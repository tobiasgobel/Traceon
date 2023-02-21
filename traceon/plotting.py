import matplotlib.tri as mtri
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.interpolate import *
import numpy as np

from .util import get_normal_3d

def _create_point_to_physical_dict(mesh):
    d = {}
    
    for k, v in mesh.cell_sets_dict.items():
        
        if 'triangle' in v: 
            for p in mesh.cells_dict['triangle'][v['triangle']]:
                a, b, c = p
                d[a], d[b], d[c] = k, k, k
        
        if 'line' in v:
            for l in mesh.cells_dict['line'][v['line']]:
                a, b = l
                d[a], d[b] = k, k
     
    return d

# Taken from
# https://stackoverflow.com/questions/13685386/matplotlib-equal-unit-length-with-equal-aspect-ratio-z-axis-is-not-equal-to
def _set_axes_equal(ax):
    """Set 3D plot axes to equal scale.

    Make axes of 3D plot have equal scale so that spheres appear as
    spheres and cubes as cubes.  Required since `ax.axis('equal')`
    and `ax.set_aspect('equal')` don't work on 3D.
    """
    limits = np.array([
        ax.get_xlim3d(),
        ax.get_ylim3d(),
        ax.get_zlim3d(),
    ])
    x, y, z = np.mean(limits, axis=1)
    radius = 0.5 * np.max(np.abs(limits[:, 1] - limits[:, 0]))
    ax.set_xlim3d([x - radius, x + radius])
    ax.set_ylim3d([y - radius, y + radius])
    ax.set_zlim3d([z - radius, z + radius])

def show_triangle_mesh(mesh, show_legend=True, show_normals=False, **colors):
    plt.figure(figsize=(10, 13))
    ax = plt.axes(projection='3d')
    plt.plot([0, 0], [0, 0], [np.min(mesh.points[:, 2]), np.max(mesh.points[:, 2])], color='black', linestyle='dashed')
    ax.set_box_aspect([1,1,1])
    _set_axes_equal(ax)
     
    plt.rcParams.update({'font.size': 17})
    
    dict_ = _create_point_to_physical_dict(mesh)
    triangles = mesh.cells_dict['triangle']
     
    triangles_to_plot = []
    colors_ = []
    
    for (A, B, C) in triangles:
        color = '#CCC'
        
        if A in dict_ and B in dict_ and C in dict_:
            phys1, phys2, phys3 = dict_[A], dict_[B], dict_[C]
            if phys1 == phys2 and phys2 == phys3 and phys1 in colors:
                color = colors[phys1]
         
        triangles_to_plot.append( [A, B, C] )
        colors_.append(color)
     
    colors_, triangles_to_plot = np.array(colors_), np.array(triangles_to_plot)
     
    for c in set(colors_):
        mask = colors_ == c
        ax.plot_trisurf(mesh.points[:, 0], mesh.points[:, 1], mesh.points[:, 2], triangles=triangles_to_plot[mask], color=c)

    if show_normals:
        normals = np.zeros( (len(triangles_to_plot), 6) )
        for i, t in enumerate(triangles_to_plot):
            v1, v2, v3 = mesh.points[t]
            middle = (v1 + v2 + v3)/3
            normal = 0.1*get_normal_3d(v1, v2, v3)
            normals[i] = [*middle, *normal]
         
        ax.quiver(*normals.T)
     
    if show_legend:
        for l, c in colors.items():
            plt.plot([], [], label=l, color=c)
        plt.legend(loc='upper left')
     
    plt.xlabel('x (mm)')
    plt.ylabel('y (mm)')
    ax.set_zlabel('z (mm)')


def show_line_mesh(mesh, trajectory=None, show_legend=True, **colors):
    plt.figure(figsize=(10, 13))
    plt.rcParams.update({'font.size': 17})
    plt.gca().set_aspect('equal')
     
    dict_ = _create_point_to_physical_dict(mesh)
    lines = mesh.cells_dict['line']

    to_plot_x = []
    to_plot_y = []
    colors_ = []
    
    for (A, B) in lines:
        color = '#CCC'

        if A in dict_ and B in dict_:
            phys1, phys2 = dict_[A], dict_[B]
            if phys1 == phys2 and phys1 in colors:
                color = colors[phys1]
         
        p1, p2 = mesh.points[A], mesh.points[B]
        to_plot_x.append( [p1[0], p2[0]] )
        to_plot_y.append( [p1[1], p2[1]] )
        colors_.append(color)
     
    colors_ = np.array(colors_)
     
    for c in set(colors_):
        mask = colors_ == c
        plt.plot(np.array(to_plot_x)[mask].T, np.array(to_plot_y)[mask].T, color=c, linewidth=2)
        plt.scatter(np.array(to_plot_x)[mask].T, np.array(to_plot_y)[mask].T, color=c, s=15)

    if show_legend:
        for l, c in colors.items():
            plt.plot([], [], label=l, color=c)
        plt.legend(loc='upper left')
     
    plt.xlabel('r (mm)')
    plt.ylabel('z (mm)')
    plt.axvline(0, color='black', linestyle='dashed')
    plt.xlim(-0.25, None)

    if trajectory is not None:
        plt.plot(trajectory[:, 0], trajectory[:, 1])

def show_charge_density(lines, charges):
    # See https://matplotlib.org/stable/gallery/lines_bars_and_markers/multicolored_line.html
    assert len(lines) == len(charges)

    plt.figure()
    segments = lines[:, :, :2] # Remove z value
    
    amplitude = np.mean(np.abs(charges))
    norm = plt.Normalize(-3*amplitude, 3*amplitude)
    
    lc = LineCollection(segments, cmap='coolwarm', norm=norm)
    lc.set_array(charges)
    lc.set_linewidth(4)
    line = plt.gca().add_collection(lc)
    plt.xlim(np.min(lines[:, :, 0])-0.2, np.max(lines[:, :, 0])+0.2)
    plt.ylim(np.min(lines[:, :, 1])-0.2, np.max(lines[:, :, 1])+0.2)
    plt.xlabel('r (mm)')
    plt.ylabel('z (mm)')
    plt.show()
    

def show(legend=False):
    if legend:
        plt.legend()
    plt.show()





