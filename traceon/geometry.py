"""The geometry module allows the creation of general meshes in 2D and 3D.
The builtin mesher uses so called _parametric_ meshes, meaning
that for any mesh we construct a mathematical formula mapping to points on the mesh. This makes it 
easy to generate structured (or transfinite) meshes. These meshes usually help the mesh to converge
to the right answer faster, since the symmetries of the mesh (radial, multipole, etc.) are better
represented. 

The parametric mesher also has downsides, since it's for example harder to generate meshes with
lots of holes in them (the 'cut' operation is not supported). For these cases, Traceon makes it easy to import
meshes generated by other programs (e.g. GMSH or Comsol). Traceon can import [meshio](https://github.com/nschloe/meshio) meshes
or any file format supported by meshio."""

from math import pi, sqrt, sin, cos, atan2, ceil

import numpy as np
from scipy.integrate import quad
from scipy.interpolate import CubicSpline

from .mesher import GeometricObject, _mesh, Mesh

__pdoc__ = {}
__pdoc__['discretize_path'] = False
__pdoc__['Path.__call__'] = True
__pdoc__['Path.__rshift__'] = True


def _points_close(p1, p2, tolerance=1e-8):
    return np.allclose(p1, p2, atol=tolerance)

def discretize_path(path_length, breakpoints, mesh_size, mesh_size_factor=None, N_factor=1):
    # Return the arguments to use to breakup the path
    # in a 'nice' way
    
    # Points that have to be in, in any case
    points = [0.] + breakpoints +  [path_length]

    subdivision = []
        
    for (u0, u1) in zip(points, points[1:]):
        if u0 == u1:
            continue
         
        if mesh_size is not None:
            N = max( ceil((u1-u0)/mesh_size), 3)
        else:
            N = 3*max(mesh_size_factor, 1)
        
        # When using higher order, we splice extra points
        # between two points in the descretization. This
        # ensures that the number of elements stays the same
        # as in the non-higher order case.
        # N_factor = 1  normal flat elements
        # N_factor = 2  extra points for curved triangles (triangle6 in GMSH terminology)
        # N_factor = 3  extra points for curved line elements (line4 in GMSH terminology)
        subdivision.append(np.linspace(u0, u1, N_factor*N, endpoint=False))
    
    subdivision.append( [path_length] )
    
    return np.concatenate(subdivision)


class Path(GeometricObject):
    """A path is a mapping from a number in the range [0, path_length] to a three dimensional point."""
    
    def __init__(self, fun, path_length, breakpoints=[], name=None):
        # Assumption: fun takes in p, the path length
        # and returns the point on the path
        self.fun = fun
        self.path_length = path_length
        assert self.path_length > 0
        self.breakpoints = breakpoints
        self.name = name
    
    def from_irregular_function(to_point, N=100, breakpoints=[]):
        """Construct a path from a function that is of the form u -> point, where 0 <= u <= 1.
        The length of the path is determined by integration.

        Parameters
        ---------------------------------
        to_point: callable
            A function accepting a number in the range [0, 1] and returns a the dimensional point.
        N: int
            Number of samples to use in the cubic spline interpolation.
        breakpoints: float iterable
            Points (0 <= u <= 1) on the path where the function is non-differentiable. These points
            are always included in the resulting mesh.

        Returns
        ---------------------------------
        Path"""
         
        # path length = integrate |f'(x)|
        fun = lambda u: np.array(to_point(u))
        
        u = np.linspace(0, 1, N)
        samples = CubicSpline(u, [fun(u_) for u_ in u])
        derivatives = samples.derivative()(u)
        norm_derivatives = np.linalg.norm(derivatives, axis=1)
        path_lengths = CubicSpline(u, norm_derivatives).antiderivative()(u)
        interpolation = CubicSpline(path_lengths, u) # Path length to [0,1]
        
        return Path(lambda pl: fun(interpolation(pl)), path_lengths[-1], breakpoints=[b*path_length for b in breakpoints])
    
    def spline_through_points(points, N=100):
        """Construct a path by fitting a cubic spline through the given points.

        Parameters
        -------------------------
        points: (N, 3) ndarray of float
            Three dimensional points through which the spline is fitted.

        Returns
        -------------------------
        Path"""

        x = np.linspace(0, 1, len(points))
        interp = CubicSpline(x, points)
        return Path.from_irregular_function(interp, N=N)
     
    def average(self, fun):
        """Average a function along the path, by integrating 1/l * fun(path(l)) with 0 <= l <= path length.

        Parameters
        --------------------------
        fun: callable (3,) -> float
            A function taking a three dimensional point and returning a float.

        Returns
        -------------------------
        float

        The average value of the function along the point."""
        return quad(lambda s: fun(self(s)), 0, self.path_length, points=self.breakpoints)[0]/self.path_length
     
    def map_points(self, fun):
        """Return a new function by mapping a function over points along the path (see `traceon.mesher.GeometricObject`).
        The path length is assumed to stay the same after this operation.
        
        Parameters
        ----------------------------
        fun: callable (3,) -> (3,)
            Function taking three dimensional points and returning three dimensional points.

        Returns
        ---------------------------
        Path"""
        return Path(lambda u: fun(self(u)), self.path_length, self.breakpoints, name=self.name)
     
    def __call__(self, t):
        """Evaluate a point along the path.

        Parameters
        ------------------------
        t: float
            The length along the path.

        Returns
        ------------------------
        (3,) float

        Three dimensional point."""
        return self.fun(t)
     
    def is_closed(self):
        """Determine whether the path is closed, by comparing the starting and endpoint.

        Returns
        ----------------------
        bool: True if the path is closed, False otherwise."""
        return _points_close(self.starting_point(), self.endpoint())
    
    def add_phase(self, l):
        """Add a phase to a closed path. A path is closed when the starting point is equal to the
        end point. A phase of length l means that the path starts 'further down' the closed path.

        Parameters
        --------------------
        l: float
            The phase (expressed as a path length). The resulting path starts l distance along the 
            original path.

        Returns
        --------------------
        Path"""
        assert self.is_closed()
        
        def fun(u):
            return self( (l + u) % self.path_length )
        
        return Path(fun, self.path_length, sorted([(b-l)%self.path_length for b in self.breakpoints + [0.]]), name=self.name)
     
    def __rshift__(self, other):
        """Combine two paths to create a single path. The endpoint of the first path needs
        to match the starting point of the second path. This common point is marked as a breakpoint and
        always included in the mesh. To use this function use the right shift operator (p1 >> p2).

        Parameters
        -----------------------
        other: Path
            The second path, to extend the current path.

        Returns
        -----------------------
        Path"""

        assert isinstance(other, Path), "Exteding path with object that is not actually a Path"

        assert _points_close(self.endpoint(), other.starting_point())

        total = self.path_length + other.path_length
         
        def f(t):
            assert 0 <= t <= total
            
            if t <= self.path_length:
                return self(t)
            else:
                return other(t - self.path_length)
        
        return Path(f, total, self.breakpoints + [self.path_length] + other.breakpoints, name=self.name)

    def starting_point(self):
        """Returns the starting point of the path.

        Returns
        ---------------------
        (3,) float

        The starting point of the path."""
        return self(0.)
    
    def middle_point(self):
        """Returns the midpoint of the path (in terms of length along the path.)

        Returns
        ----------------------
        (3,) float
        
        The point at the middle of the path."""
        return self(self.path_length/2)
    
    def endpoint(self):
        """Returns the endpoint of the path.

        Returns
        ------------------------
        (3,) float
        
        The endpoint of the path."""
        return self(self.path_length)
    
    def line_to(self, point):
        """Extend the current path by a line from the current endpoint to the given point.
        The given point is marked a breakpoint.

        Parameters
        ----------------------
        point: (3,) float
            The new endpoint.

        Returns
        ---------------------
        Path"""
        point = np.array(point)
        assert point.shape == (3,), "Please supply a three dimensional point to .line_to(...)"
        l = Path.line(self.endpoint(), point)
        return self >> l
     
    def circle_xz(x0, z0, radius, angle=2*pi):
        """Returns (part of) a circle in the XZ plane around the x-axis. Starting on the positive x-axis.
        
        Parameters
        --------------------------------
        x0: float
            x-coordinate of the center of the circle
        z0: float
            z-coordiante of the center of the circle
        radius: float
            radius of the circle
        angle: float
            The circumference of the circle in radians. The default of 2*pi gives a full circle.

        Returns
        ---------------------------------
        Path"""
        def f(u):
            theta = u / radius 
            return np.array([radius*cos(theta), 0., radius*sin(theta)])
        return Path(f, angle*radius).move(dx=x0, dz=z0)
    
    def circle_yz(y0, z0, radius, angle=2*pi):
        """Returns (part of) a circle in the YZ plane around the x-axis. Starting on the positive y-axis.
        
        Parameters
        --------------------------------
        y0: float
            x-coordinate of the center of the circle
        z0: float
            z-coordiante of the center of the circle
        radius: float
            radius of the circle
        angle: float
            The circumference of the circle in radians. The default of 2*pi gives a full circle.

        Returns
        ---------------------------------
        Path"""
        def f(u):
            theta = u / radius 
            return np.array([0., radius*cos(theta), radius*sin(theta)])
        return Path(f, angle*radius).move(dy=y0, dz=z0)
    
    def circle_xy(x0, y0, radius, angle=2*pi):
        """Returns (part of) a circle in the XY plane around the z-axis. Starting on the positive X-axis.
        
        Parameters
        --------------------------------
        y0: float
            x-coordinate of the center of the circle
        y0: float
            y-coordiante of the center of the circle
        radius: float
            radius of the circle
        angle: float
            The circumference of the circle in radians. The default of 2*pi gives a full circle.

        Returns
        ---------------------------------
        Path"""
        def f(u):
            theta = u / radius 
            return np.array([radius*cos(theta), radius*sin(theta), 0.])
        return Path(f, angle*radius).move(dx=x0, dy=y0)
     
    def arc_to(self, center, end, reverse=False):
        """Extend the current path using an arc.

        Parameters
        ----------------------------
        center: (3,) float
            The center point of the arc.
        end: (3,) float
            The endpoint of the arc, shoud lie on a circle determined
            by the given centerpoint and the current endpoint.

        Returns
        -----------------------------
        Path"""
        start = self.endpoint()
        return self >> Path.arc(center, start, end, reverse=reverse)
    
    def arc(center, start, end, reverse=False):
        """Return an arc by specifying the center, start and end point.

        Parameters
        ----------------------------
        center: (3,) float
            The center point of the arc.
        start: (3,) float
            The start point of the arc.
        end: (3,) float
            The endpoint of the arc.

        Returns
        ----------------------------
        Path"""
        start, center, end = np.array(start), np.array(center), np.array(end)
         
        x_unit = start - center
        x_unit /= np.linalg.norm(x_unit)

        vector = end - center
         
        y_unit = vector - np.dot(vector, x_unit) * x_unit
        y_unit /= np.linalg.norm(y_unit)

        radius = np.linalg.norm(start - center) 
        theta_max = atan2(np.dot(vector, y_unit), np.dot(vector, x_unit))

        if reverse:
            theta_max = theta_max - 2*pi

        path_length = abs(theta_max * radius)
          
        def f(l):
            theta = l/path_length * theta_max
            return center + radius*cos(theta)*x_unit + radius*sin(theta)*y_unit
        
        return Path(f, path_length)
     
    def revolve_x(self, angle=2*pi):
        """Create a surface by revolving the path anti-clockwise around the x-axis.
        
        Parameters
        -----------------------
        angle: float
            The angle by which to revolve. THe default 2*pi gives a full revolution.

        Returns
        -----------------------
        Surface"""
        
        pstart, pmiddle, pend = self.starting_point(), self.middle_point(), self.endpoint()
        r_avg = self.average(lambda p: sqrt(p[1]**2 + p[2]**2))
        length2 = 2*pi*r_avg
         
        def f(u, v):
            p = self(u)
            theta = atan2(p[2], p[1])
            r = sqrt(p[1]**2 + p[2]**2)
            return np.array([p[0], r*cos(theta + v/length2*angle), r*sin(theta + v/length2*angle)])
         
        return Surface(f, self.path_length, length2, self.breakpoints, name=self.name)
    
    def revolve_y(self, angle=2*pi):
        """Create a surface by revolving the path anti-clockwise around the y-axis.
        
        Parameters
        -----------------------
        angle: float
            The angle by which to revolve. THe default 2*pi gives a full revolution.

        Returns
        -----------------------
        Surface"""

        pstart, pend = self.starting_point(), self.endpoint()
        r_avg = self.average(lambda p: sqrt(p[0]**2 + p[2]**2))
        length2 = 2*pi*r_avg
         
        def f(u, v):
            p = self(u)
            theta = atan2(p[2], p[0])
            r = sqrt(p[0]*p[0] + p[2]*p[2])
            return np.array([r*cos(theta + v/length2*angle), p[1], r*sin(theta + v/length2*angle)])
         
        return Surface(f, self.path_length, length2, self.breakpoints, name=self.name)
    
    def revolve_z(self, angle=2*pi):
        """Create a surface by revolving the path anti-clockwise around the z-axis.
        
        Parameters
        -----------------------
        angle: float
            The angle by which to revolve. THe default 2*pi gives a full revolution.

        Returns
        -----------------------
        Surface"""

        pstart, pend = self.starting_point(), self.endpoint()
        r_avg = self.average(lambda p: sqrt(p[0]**2 + p[1]**2))
        length2 = 2*pi*r_avg
        
        def f(u, v):
            p = self(u)
            theta = atan2(p[1], p[0])
            r = sqrt(p[0]*p[0] + p[1]*p[1])
            return np.array([r*cos(theta + v/length2*angle), r*sin(theta + v/length2*angle), p[2]])
        
        return Surface(f, self.path_length, length2, self.breakpoints, name=self.name)
     
    def extrude(self, vector):
        """Create a surface by extruding the path along a vector. The vector gives both
        the length and the direction of the extrusion.

        Parameters
        -------------------------
        vector: (3,) float
            The direction and length (norm of the vector) to extrude by.

        Returns
        -------------------------
        Surface"""
        vector = np.array(vector)
        length = np.linalg.norm(vector)
         
        def f(u, v):
            return self(u) + v/length*vector
        
        return Surface(f, self.path_length, length, self.breakpoints, name=self.name)
    
    def extrude_by_path(self, p2):
        """Create a surface by extruding the path along a second path. The second
        path does not need to start along the first path. Imagine the surface created
        by moving the first path along the second path.

        Parameters
        -------------------------
        p2: Path
            The (second) path defining the extrusion.

        Returns
        ------------------------
        Surface"""
        p0 = p2.starting_point()
         
        def f(u, v):
            return self(u) + p2(v) - p0

        return Surface(f, self.path_length, p2.path_length, self.breakpoints, p2.breakpoints, name=self.name)

    def close(self):
        """Close the path, by making a straight line to the starting point.

        Returns
        -------------------
        Path"""
        return self.line_to(self.starting_point())
    
    def ellipse(major, minor):
        """Create a path along the outline of an ellipse. The ellipse lies
        in the XY plane, and the path starts on the positive x-axis.

        Parameters
        ---------------------------
        major: float
            The major axis of the ellipse (lies along the x-axis).
        minor: float
            The minor axis of the ellipse (lies along the y-axis).

        Returns
        ---------------------------
        Path"""
        # Crazy enough there is no closed formula
        # to go from path length to a point on the ellipse.
        # So we have to use `from_irregular_function`
        def f(u):
            return np.array([major*cos(2*pi*u), minor*sin(2*pi*u), 0.])
        return Path.from_irregular_function(f)
    
    def line(from_, to):
        """Create a straight line between two points.

        Parameters
        ------------------------------
        from_: (3,) float
            The starting point of the path.
        to: (3,) float
            The endpoint of the path.

        Returns
        ---------------------------
        Path"""
        from_, to = np.array(from_), np.array(to)
        length = np.linalg.norm(from_ - to)
        return Path(lambda pl: (1-pl/length)*from_ + pl/length*to, length)

    def cut(self, length):
        """Cut the path in two at a specific length along the path.

        Parameters
        --------------------------------------
        length: float
            The length along the path at which to cut.

        Returns
        -------------------------------------
        (Path, Path)
        
        A tuple containing two paths. The first path contains the path upto length, while the second path contains the rest."""
        return (Path(self.fun, length, [b for b in self.breakpoints if b <= length], name=self.name),
                Path(lambda l: self.fun(l + length), self.path_length - length, [b - length for b in self.breakpoints if b >= length], name=self.name))
    
    def rectangle_xz(xmin, xmax, zmin, zmax):
        """Create a rectangle in the XZ plane. The path starts at (xmin, 0, zmin), and is 
        counter clockwise around the y-axis.
        
        Parameters
        ------------------------
        xmin: float
            Minimum x-coordinate of the corner points.
        xmax: float
            Maximum x-coordinate of the corner points.
        zmin: float
            Minimum z-coordinate of the corner points.
        zmax: float
            Maximum z-coordinate of the corner points.
        
        Returns
        -----------------------
        Path"""
        return Path.line([xmin, 0., zmin], [xmax, 0, zmin]) \
            .line_to([xmax, 0, zmax]).line_to([xmin, 0., zmax]).close()
     
    def rectangle_yz(ymin, ymax, zmin, zmax):
        """Create a rectangle in the YZ plane. The path starts at (0, ymin, zmin), and is 
        counter clockwise around the x-axis.
        
        Parameters
        ------------------------
        ymin: float
            Minimum y-coordinate of the corner points.
        ymax: float
            Maximum y-coordinate of the corner points.
        zmin: float
            Minimum z-coordinate of the corner points.
        zmax: float
            Maximum z-coordinate of the corner points.
        
        Returns
        -----------------------
        Path"""

        return Path.line([0., ymin, zmin], [0, ymin, zmax]) \
            .line_to([0., ymax, zmax]).line_to([0., ymax, zmin]).close()
     
    def rectangle_xy(xmin, xmax, ymin, ymax):
        """Create a rectangle in the XY plane. The path starts at (xmin, ymin, 0), and is 
        counter clockwise around the z-axis.
        
        Parameters
        ------------------------
        xmin: float
            Minimum x-coordinate of the corner points.
        xmax: float
            Maximum x-coordinate of the corner points.
        ymin: float
            Minimum y-coordinate of the corner points.
        ymax: float
            Maximum y-coordinate of the corner points.
        
        Returns
        -----------------------
        Path"""
        return Path.line([xmin, ymin, 0.], [xmin, ymax, 0.]) \
            .line_to([xmax, ymax, 0.]).line_to([xmax, ymin, 0.]).close()
    
    def aperture(height, radius, extent, z=0.):
        """Create an 'aperture'. Note that in a radially symmetric geometry
        an aperture is basically a rectangle with the right side 'open'. Revolving
        this path around the z-axis would generate a cylindircal hole in the center. 
        This is the most basic model of an aperture.

        Parameters
        ------------------------
        height: float
            The height of the aperture
        radius: float
            The radius of the aperture hole (distance to the z-axis)
        extent: float
            The maximum x value
        z: float
            The z-coordinate of the center of the aperture

        Returns
        ------------------------
        Path"""
        return Path.line([extent, 0., -height/2], [radius, 0., -height/2])\
                .line_to([radius, 0., height/2]).line_to([extent, 0., height/2]).move(dz=z)
    
    def __add__(self, other):
        """Add two paths to create a PathCollection. Note that a PathCollection supports
        a subset of the methods of Path (for example, movement, rotation and meshing). Use
        the + operator to combine paths into a path collection: path1 + path2 + path3.

        Returns
        -------------------------
        PathCollection"""
         
        if not isinstance(other, Path) and not isinstance(other, PathCollection):
            return NotImplemented
        
        if isinstance(other, Path):
            return PathCollection([self, other])
        elif isinstance(other, PathCollection):
            return PathCollection([self] + [other.paths])
     
    def mesh(self, mesh_size=None, mesh_size_factor=None, higher_order=False):
        """Mesh the path, so it can be used in the BEM solver.

        Parameters
        --------------------------
        mesh_size: float
            Determines amount of elements in the mesh. A smaller
            mesh size leads to more elements.
        mesh_size_factor: float
            Alternative way to specify the mesh size, which scales
            with the dimensions of the geometry, and therefore more
            easily translates between different geometries.
        higher_order: bool
            Whether to generate a higher order mesh. A higher order
            produces curved line elements (determined by 4 points on
            each curved element). The BEM solver supports higher order
            elements in radial symmetric geometries only.

        Returns
        ----------------------------
        Path"""
        u = discretize_path(self.path_length, self.breakpoints, mesh_size, mesh_size_factor, N_factor=3 if higher_order else 1)
        
        N = len(u) 
        points = np.zeros( (N, 3) )
         
        for i in range(N):
            points[i] = self(u[i])
         
        if not higher_order:
            lines = np.array([np.arange(N-1), np.arange(1, N)]).T
        else:
            assert N % 3 == 1
            r = np.arange(N)
            p0 = r[0:-1:3]
            p1 = r[3::3]
            p2 = r[1::3]
            p3 = r[2::3]
            lines = np.array([p0, p1, p2, p3]).T
          
        assert lines.dtype == np.int64
         
        if self.name is not None:
            physical_to_lines = {self.name:np.arange(len(lines))}
        else:
            physical_to_lines = {}
        
        return Mesh(points=points, lines=lines, physical_to_lines=physical_to_lines)


class PathCollection(GeometricObject):
    
    def __init__(self, paths):
        assert all([isinstance(p, Path) for p in paths])
        self.paths = paths
        self.name = None
    
    def map_points(self, fun):
        return PathCollection([p.map_points(fun) for p in self.paths])
     
    def mesh(self, mesh_size=None, mesh_size_factor=None, higher_order=False):
        mesh = Mesh()
        
        for p in self.paths:
            if self.name is not None:
                p.name = self.name
            mesh = mesh + p.mesh(mesh_size=mesh_size, mesh_size_factor=mesh_size_factor, higher_order=higher_order)

        return mesh

    def _map_to_surfaces(self, f, *args, **kwargs):
        surfaces = []

        for p in self.paths:
            surfaces.append(f(p, *args, **kwargs))

        return SurfaceCollection(surfaces)
    
    def __add__(self, other):
        if not isinstance(other, Path) and not isinstance(other, PathCollection):
            return NotImplemented
        
        if isinstance(other, Path):
            return PathCollection(self.paths+[other])
        else:
            return PathCollection(self.paths+other.paths)
      
    def __iadd__(self, other):
        assert isinstance(other, PathCollection) or isinstance(other, Path)

        if isinstance(other, Path):
            self.paths.append(other)
        else:
            self.paths.extend(other.paths)
       
    def revolve_x(self, angle=2*pi):
        return self._map_to_surfaces(Path.revolve_x, angle=angle)
    def revolve_y(self, angle=2*pi):
        return self._map_to_surfaces(Path.revolve_y, angle=angle)
    def revolve_z(self, angle=2*pi):
        return self._map_to_surfaces(Path.revolve_z, angle=angle)
    def extrude(self, vector):
        return self._map_to_surface(Path.extrude, vector)
    def extrude_by_path(self, p2):
        return self._map_to_surface(Path.extrude_by_path, p2)
     


class Surface(GeometricObject):
    def __init__(self, fun, path_length1, path_length2, breakpoints1=[], breakpoints2=[], name=None):
        self.fun = fun
        self.path_length1 = path_length1
        self.path_length2 = path_length2
        assert self.path_length1 > 0 and self.path_length2 > 0
        self.breakpoints1 = breakpoints1
        self.breakpoints2 = breakpoints2
        self.name = name

    def sections(self): 
        # Iterate over the sections defined by
        # the breakpoints
        b1 = [0.] + self.breakpoints1 + [self.path_length1]
        b2 = [0.] + self.breakpoints2 + [self.path_length2]

        for u0, u1 in zip(b1[:-1], b1[1:]):
            for v0, v1 in zip(b2[:-1], b2[1:]):
                def fun(u, v, u0_=u0, v0_=v0):
                    return self(u0_+u, v0_+v)
                yield Surface(fun, u1-u0, v1-v0, [], [])
       
    def __call__(self, u, v):
        return self.fun(u, v)

    def map_points(self, fun):
        return Surface(lambda u, v: fun(self(u, v)),
            self.path_length1, self.path_length2,
            self.breakpoints1, self.breakpoints2)
     
    def spanned_by_paths(path1, path2):
        length1 = max(path1.path_length, path2.path_length)
        
        length_start = np.linalg.norm(path1.starting_point() - path2.starting_point())
        length_final = np.linalg.norm(path1.endpoint() - path2.endpoint())
        length2 = (length_start + length_final)/2
         
        def f(u, v):
            p1 = path1(u/length1*path1.path_length) # u/l*p = b, u = l*b/p
            p2 = path2(u/length1*path2.path_length)
            return (1-v/length2)*p1 + v/length2*p2

        breakpoints = sorted([length1*b/path1.path_length for b in path1.breakpoints] + \
                                [length1*b/path2.path_length for b in path2.breakpoints])
         
        return Surface(f, length1, length2, breakpoints)

    def sphere(radius):
        
        length1 = 2*pi*radius
        length2 = pi*radius
         
        def f(u, v):
            phi = u/radius
            theta = v/radius
            
            return np.array([
                radius*sin(theta)*cos(phi),
                radius*sin(theta)*sin(phi),
                radius*cos(theta)]) 
        
        return Surface(f, length1, length2)

    def from_boundary_paths(p1, p2, p3, p4):
        path_length_p1_and_p3 = (p1.path_length + p3.path_length)/2
        path_length_p2_and_p4 = (p2.path_length + p4.path_length)/2

        def f(u, v):
            u /= path_length_p1_and_p3
            v /= path_length_p2_and_p4
            
            a = (1-v)
            b = (1-u)
             
            c = v
            d = u
            
            return 1/2*(a*p1(u*p1.path_length) + \
                        b*p4((1-v)*p4.path_length) + \
                        c*p3((1-u)*p3.path_length) + \
                        d*p2(v*p2.path_length))
        
        # Scale the breakpoints appropriately
        b1 = sorted([b/p1.path_length * path_length_p1_and_p3 for b in p1.breakpoints] + \
                [b/p3.path_length * path_length_p1_and_p3 for b in p3.breakpoints])
        b2 = sorted([b/p2.path_length * path_length_p2_and_p4 for b in p2.breakpoints] + \
                [b/p4.path_length * path_length_p2_and_p4 for b in p4.breakpoints])
        
        return Surface(f, path_length_p1_and_p3, path_length_p2_and_p4, b1, b2)
     
    def disk_xz(x0, z0, radius):
        """Create a disk in the XZ plane.         
        
        Parameters
        ------------------------
        x0: float
            x-coordiante of the center of the disk
        z0: float
            z-coordinate of the center of the disk
        radius: float
            radius of the disk
        Returns
        -----------------------
        Surface"""
        assert radius > 0, "radius must be a positive number"
        disk_at_origin = Path.line([0.0, 0.0, 0.0], [radius, 0.0, 0.0]).revolve_y()
        return disk_at_origin.move(dx=x0, dz=z0)
    
    def disk_yz(y0, z0, radius):
        """Create a disk in the YZ plane.         
        
        Parameters
        ------------------------
        y0: float
            y-coordiante of the center of the disk
        z0: float
            z-coordinate of the center of the disk
        radius: float
            radius of the disk
        Returns
        -----------------------
        Surface"""
        assert radius > 0, "radius must be a positive number"
        disk_at_origin = Path.line([0.0, 0.0, 0.0], [0.0, radius, 0.0]).revolve_x()
        return disk_at_origin.move(dy=y0, dz=z0)

    def disk_xy(x0, y0, radius):
        """Create a disk in the XY plane.
        
        Parameters
        ------------------------
        x0: float
            x-coordiante of the center of the disk
        y0: float
            y-coordinate of the center of the disk
        radius: float
            radius of the disk
        Returns
        -----------------------
        Surface"""
        assert radius > 0, "radius must be a positive number"
        disk_at_origin = Path.line([0.0, 0.0, 0.0], [radius, 0.0, 0.0]).revolve_z()
        return disk_at_origin.move(dx=x0, dy=y0)
     
    def rectangle_xz(xmin, xmax, zmin, zmax):
        """Create a rectangle in the XZ plane. The path starts at (xmin, 0, zmin), and is 
        counter clockwise around the y-axis.
        
        Parameters
        ------------------------
        xmin: float
            Minimum x-coordinate of the corner points.
        xmax: float
            Maximum x-coordinate of the corner points.
        zmin: float
            Minimum z-coordinate of the corner points.
        zmax: float
            Maximum z-coordinate of the corner points.
        
        Returns
        -----------------------
        Surface representing the rectangle"""
        return Path.line([xmin, 0., zmin], [xmin, 0, zmax]).extrude([xmax-xmin, 0., 0.])
     
    def rectangle_yz(ymin, ymax, zmin, zmax):
        """Create a rectangle in the YZ plane. The path starts at (0, ymin, zmin), and is 
        counter clockwise around the x-axis.
        
        Parameters
        ------------------------
        ymin: float
            Minimum y-coordinate of the corner points.
        ymax: float
            Maximum y-coordinate of the corner points.
        zmin: float
            Minimum z-coordinate of the corner points.
        zmax: float
            Maximum z-coordinate of the corner points.
        
        Returns
        -----------------------
        Surface representing the rectangle"""
        return Path.line([0., ymin, zmin], [0., ymin, zmax]).extrude([0., ymax-ymin, 0.])
     
    def rectangle_xy(xmin, xmax, ymin, ymax):
        """Create a rectangle in the XY plane. The path starts at (xmin, ymin, 0), and is 
        counter clockwise around the z-axis.
        
        Parameters
        ------------------------
        xmin: float
            Minimum x-coordinate of the corner points.
        xmax: float
            Maximum x-coordinate of the corner points.
        ymin: float
            Minimum y-coordinate of the corner points.
        ymax: float
            Maximum y-coordinate of the corner points.
        
        Returns
        -----------------------
        Surface representing the rectangle"""
        return Path.line([xmin, ymin, 0.], [xmin, ymax, 0.]).extrude([xmax-xmin, 0., 0.])

    def aperture(height, radius, extent, z=0.):
        return Path.aperture(height, radius, extent, z=z).revolve_z()
     
    def __add__(self, other):
        if not isinstance(other, Surface) and not isinstance(other, SurfaceCollection):
            return NotImplemented

        if isinstance(other, Surface):
            return SurfaceCollection([self, other])
        else:
            return SurfaceCollection([self] + other.surfaces)
     
    def mesh(self, mesh_size=None, mesh_size_factor=None):
          
        if mesh_size is None:
            path_length = min(self.path_length1, self.path_length2)
             
            mesh_size = path_length / 4

            if mesh_size_factor is not None:
                mesh_size /= sqrt(mesh_size_factor)
         
        return _mesh(self, mesh_size, name=self.name)



class SurfaceCollection(GeometricObject):
     
    def __init__(self, surfaces):
        assert all([isinstance(s, Surface) for s in surfaces])
        self.surfaces = surfaces
        self.name = None
     
    def map_points(self, fun):
        return SurfaceCollection([s.map_points(fun) for s in self.surfaces])
     
    def mesh(self, mesh_size=None, mesh_size_factor=None, name=None):
        mesh = Mesh()
        
        for s in self.surfaces:
            if self.name is not None:
                s.name = self.name
            
            mesh = mesh + s.mesh(mesh_size=mesh_size, mesh_size_factor=mesh_size_factor)
         
        return mesh
     
    def __add__(self, other):
        if not isinstance(other, Surface) and not isinstance(other, SurfaceCollection):
            return NotImplemented
              
        if isinstance(other, Surface):
            return SurfaceCollection(self.surfaces+[other])
        else:
            return SurfaceCollection(self.surfaces+other.surfaces)
     
    def __iadd__(self, other):
        assert isinstance(other, SurfaceCollection) or isinstance(other, Surface)
        
        if isinstance(other, Surface):
            self.surfaces.append(other)
        else:
            self.surfaces.extend(other.surfaces)
    







