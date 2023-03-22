# Traceon

Traceon is a general software package for numerical electron optics. The heart of the package is an implementation of the Boundary Element Method (BEM) to efficiently compute the surface charge distribution. Currently radial symmetry and general three dimensional geometries are supported. In both symmetries very accuracute and efficient radial series interpolation can be used to make electron tracing very fast. The resulting electron trajectories can be used to determine the aberrations of optical components under study.

Traceon is completely free to use and open source. The source code is distributed under the `AGPLv3` license.

## Documentation

[Examples](https://github.com/leon-vv/Traceon/tree/main/examples)

[API documentation](https://leon.science/traceon/index.html)

## License

[AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)

## Installation

Install using the Python package manager:
```
pip install traceon
```

The installation is known to work on Linux and Windows. Please reach out to me if you have any installation problems (see below).

## Help! I have a problem!

Don't worry. You can reach me.

[Open an issue](https://github.com/leon-vv/Traceon/issues)

[Send me an email](mailto:leonvanvelzen@protonmail.com)

## Features

- Uses the powerful [GMSH library](https://gmsh.info/) for meshing
- Solve for surface charge distribution using BEM
- General 3D geometries and radially symmetric geometries
- Dielectrics
- Floating conductors
- Accurate electron tracing using adaptive time steps
- Field/potential calculation by integration over surface charges
- Fast field/potential calculation by radial series expansion
- Superposition of electrostatic fields

## Validations

To ensure the accuracy of the package, different problems from the literature have been analyzed using this software. See `/validations` directory for more information. The validations can easily be executed from the command line, for example:
```bash
python3 ./validation/edwards2007.py --help
```


