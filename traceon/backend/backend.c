#include <stdio.h>
#include <assert.h>
#include <math.h>
#include <stdlib.h>

// https://stackoverflow.com/questions/752309/ensuring-c-doubles-are-64-bits
#ifndef __STDC_IEC_559__
#error "Requires IEEE 754 floating point!"
#endif

#define DERIVS_MAX_2D 9
#define DERIV_3D_MAX 9
#define NU_MAX (DERIV_3D_MAX/2)
#define M_MAX DERIV_3D_MAX
#define N_TRIANGLE_QUAD 9

#define TRACING_STEP_MAX 0.085
#define TRACING_STEP_MIN (TRACING_STEP_MAX/1e10)

#define MIN_DISTANCE_AXIS 1e-10

#ifndef M_PI
    #define M_PI 3.14159265358979323846
#endif

//////////////////////////////// ELLIPTIC FUNCTIONS

// Chebyshev Approximations for the Complete Elliptic Integrals K and E.
// W. J. Cody. 1965.
//
// Augmented with the tricks shown on the Scipy documentation for ellipe and ellipk.


double ellipk_singularity(double k) {
	double eta = 1 - k;
	
	double A[] = {log(4),
			9.65736020516771e-2,
			3.08909633861795e-2,
			1.52618320622534e-2,
			1.25565693543211e-2,
			1.68695685967517e-2,
			1.09423810688623e-2,
			1.40704915496101e-3};
	
	double B[] = {1/2,
			1.24999998585309e-1,
			7.03114105853296e-2,
			4.87379510945218e-2,
			3.57218443007327e-2,
			2.09857677336790e-2,
			5.81807961871996e-3,
			3.42805719229748e-4};
		
	return A[0] + A[1]*eta + A[2]*pow(eta,2) + A[3]*pow(eta,3) + A[4]*pow(eta,4) + A[5]*pow(eta,5) + A[6]*pow(eta,6) + A[7]*pow(eta,7) 
                + log(1/eta)*(B[0] + B[1]*eta + B[2]*pow(eta,2) + B[3]*pow(eta,3) + B[4]*pow(eta,4) + B[5]*pow(eta,5) + B[6]*pow(eta,6) + B[7]*pow(eta,7));

}

double ellipk(double k) {
	if(k > -1) return ellipk_singularity(k);
	
	return ellipk_singularity(1 - 1/(1-k))/sqrt(1-k);
}

double ellipe_01(double k) {
	double eta = 1 - k;
	
	double A[] = {1,
        4.43147193467733e-1,
        5.68115681053803e-2,
        2.21862206993846e-2,
        1.56847700239786e-2,
        1.92284389022977e-2,
        1.21819481486695e-2,
        1.55618744745296e-3};

    double B[] = {0,
        2.49999998448655e-1,
        9.37488062098189e-2,
        5.84950297066166e-2,
        4.09074821593164e-2,
        2.35091602564984e-2,
        6.45682247315060e-3,
        3.78886487349367e-4};
	
	return A[0] + A[1]*eta + A[2]*pow(eta,2) + A[3]*pow(eta,3) + A[4]*pow(eta,4) + A[5]*pow(eta,5) + A[6]*pow(eta,6) + A[7]*pow(eta,7) 
                + log(1/eta)*(B[0] + B[1]*eta + B[2]*pow(eta,2) + B[3]*pow(eta,3) + B[4]*pow(eta,4) + B[5]*pow(eta,5) + B[6]*pow(eta,6) + B[7]*pow(eta,7));
}

double ellipe(double k) {
	if (0 <= k && k <= 1) return ellipe_01(k);

	return ellipe_01(k/(k-1))*sqrt(1-k);

}


//////////////////////////////// UTILITIES 2D

typedef double (*integration_cb_2d)(double, double, double, double, void*);


double
norm_2d(double x, double y) {
	return sqrt(x*x + y*y);
}

void
normal_2d(double *p1, double *p2, double *normal) {
	double x1 = p1[0], y1 = p1[1];
	double x2 = p2[0], y2 = p2[1];
	
	double tangent_x = x2 - x1, tangent_y = y2 - y1;
	double normal_x = tangent_y, normal_y = -tangent_x;
	double length = norm_2d(normal_x, normal_y);

	normal[0] = normal_x/length;
	normal[1] = normal_y/length;
}

double
line_integral(double target[2], double v1[2], double v2[2], integration_cb_2d function, void* args) {
    
    double target_x = target[0], target_y = target[1];
    double source_x1 = v1[0], source_y1 = v1[1];
    double source_x2 = v2[0], source_y2 = v2[1];
     
    double middle_x = (source_x2 + source_x1)/2;
    double middle_y = (source_y1 + source_y2)/2;
    double length = norm_2d(source_x2 - source_x1, source_y2 - source_y1);
    double distance = norm_2d(middle_x - target_x, middle_y - target_y);
     
    if(distance > 20*length) {
        // Speedup, just consider middle point
        return function(target_x, target_y, middle_x, middle_y, args) * length;
	}
    else {
        size_t N_int = 256;
		assert((N_int-1)%3 == 0);
		
		double dx = (source_x2 - source_x1)/(N_int-1);
		double dy = (source_y2 - source_y1)/(N_int-1);
		
		int i = 1;
		double sum_ = function(target_x, target_y, source_x1, source_y1, args);
		while(i < N_int-1) {
			double xi = source_x1 + dx*i, yi = source_y1 + dy*i;
			double xi1 = source_x1 + dx*(i+1), yi1 = source_y1 + dy*(i+1);
			double xi2 = source_x1 + dx*(i+2), yi2 = source_y1 + dy*(i+2);
			
			double fi = function(target_x, target_y, xi, yi, args);
			double fi1 = function(target_x, target_y, xi1, yi1, args);
			double fi2 = function(target_x, target_y, xi2, yi2, args);
			
			sum_ += 3*fi + 3*fi1 + 2*fi2;
			i += 3;
		}
		
		assert(i == N_int);
		
		// Last one is counted double in the previous iteration
		sum_ -= function(target_x, target_y, source_x1 + dx*(i-1), source_y1 + dy*(i-1), args);
		
		double dline = norm_2d(dx, dy);
		sum_ *= dline*3/8;
		
		return sum_;
	}
}

//////////////////////////////// UTILITIES 3D


typedef double (*integration_cb_3d)(double, double, double, double, double, double, void*);

double
norm_3d(double x, double y, double z) {
	return sqrt(x*x + y*y + z*z);
}

void
normal_3d(double *p1, double *p2, double *p3, double *normal) {
	double x1 = p1[0], y1 = p1[1], z1 = p1[2];
	double x2 = p2[0], y2 = p2[1], z2 = p2[2];
	double x3 = p3[0], y3 = p3[1], z3 = p3[2];

	double normal_x = (y2-y1)*(z3-z1)-(y3-y1)*(z2-z1);
	double normal_y = (x3-x1)*(z2-z1)-(x2-x1)*(z3-z1);
	double normal_z = (x2-x1)*(y3-y1)-(x3-x1)*(y2-y1);
	double length = norm_3d(normal_x, normal_y, normal_z);
	
	normal[0] = normal_x/length;
	normal[1] = normal_y/length;
	normal[2] = normal_z/length;
}

// Triangle quadrature constants
double QUAD_B1[N_TRIANGLE_QUAD] = {0.124949503233232, 0.437525248383384, 0.437525248383384, 0.797112651860071, 0.797112651860071, 0.165409927389841, 0.165409927389841, 0.037477420750088, 0.037477420750088};
double QUAD_B2[N_TRIANGLE_QUAD] = {0.437525248383384, 0.124949503233232, 0.437525248383384, 0.165409927389841, 0.037477420750088, 0.797112651860071, 0.037477420750088, 0.797112651860071, 0.165409927389841};
double QUAD_WEIGHTS[N_TRIANGLE_QUAD] = {0.205950504760887, 0.205950504760887, 0.205950504760887, 0.063691414286223, 0.063691414286223, 0.063691414286223, 0.063691414286223, 0.063691414286223, 0.063691414286223};

double
triangle_integral(double target[3], double v1[3], double v2[3], double v3[3], integration_cb_3d function, void *args) {
	double v1x = v1[0], v1y = v1[1], v1z = v1[2];
	double v2x = v2[0], v2y = v2[1], v2z = v2[2];
	double v3x = v3[0], v3y = v3[1], v3z = v3[2];
		
	double area = 0.5*sqrt(pow((v2y-v1y)*(v3z-v1z)-(v2z-v1z)*(v3y-v1y), 2) + pow((v2z-v1z)*(v3x-v1x)-(v2x-v1x)*(v3z-v1z), 2) + pow((v2x-v1x)*(v3y-v1y)-(v2y-v1y)*(v3x-v1x), 2));
	
	double sum_ = 0.0;
	
	for (int k=0; k < N_TRIANGLE_QUAD; k++) {
		double b1_ = QUAD_B1[k];
		double b2_ = QUAD_B2[k];
		double w = QUAD_WEIGHTS[k];
			
        double x = v1x + b1_*(v2x-v1x) + b2_*(v3x-v1x);
        double y = v1y + b1_*(v2y-v1y) + b2_*(v3y-v1y);
        double z = v1z + b1_*(v2z-v1z) + b2_*(v3z-v1z);
			
        sum_ += w*function(target[0], target[1], target[2], x, y, z, args);
	}
	      
    return area*sum_;
}


//////////////////////////////// PARTICLE TRACING


double EM = -0.1758820022723908; // e/m units ns and mm

double A[]  = {0.0, 2/9, 1/3, 3/4, 1, 5/6};		// https://en.wikipedia.org/wiki/Runge%E2%80%93Kutta%E2%80%93Fehlberg_method
double B6[] = {65/432, -5/16, 13/16, 4/27, 5/144};
double B5[] = {-17/12, 27/4, -27/5, 16/15};
double B4[] = {69/128, -243/128, 135/64};
double B3[] = {1/12, 1/4};
double B2[] = {2/9};
double CH[] = {47/450, 0, 12/25, 32/225, 1/30, 6/25};
double CT[] = {-1/150, 0, 3/100, -16/75, -1/20, 6/25};

size_t TRACING_BLOCK_SIZE = (size_t) 1e5;

typedef void (*field_fun)(double pos[6], double field[3], void* args);

void
produce_new_y(double y[6], double ys[6][6], double ks[6][6], size_t index) {
	
	double* coefficients[] = {NULL, B2, B3, B4, B5, B6};
	
	for(int i = 0; i < 6; i++) {
		
		ys[index][i] = y[i];
		
		for(int j = 0; j < index; j++) 
			ys[index][i] += coefficients[index][j]*ks[j][i];
	}
}

void
produce_new_k(double ys[6][6], double ks[6][6], size_t index, double h, field_fun ff, void *args) {
	
	double field[3];
	ff(ys[index], field, args);

	ks[index][0] = h*ks[index-1][3];
	ks[index][1] = h*ks[index-1][4];
	ks[index][2] = h*ks[index-1][5];
	ks[index][3] = h*EM*field[0];
	ks[index][4] = h*EM*field[1];
	ks[index][5] = h*EM*field[2];
}


size_t
trace_particle(double *pos_array, field_fun field, double bounds[3][2], double atol, void *args) {
	
	double (*positions)[6] = (double (*)[6]) pos_array;
	
	double y[6];
	for(int i = 0; i < 6; i++) y[i] = positions[0][i];
		
    double V = norm_3d(y[3], y[4], y[5]);
    double h = TRACING_STEP_MAX/V;
    double hmax = TRACING_STEP_MAX/V;
    double hmin = TRACING_STEP_MIN/V;
     
    int N = 1;
		
    double xmin = bounds[0][0], xmax = bounds[0][1];
	double ymin = bounds[1][0], ymax = bounds[1][1];
	double zmin = bounds[2][0], zmax = bounds[2][1];

	 
    while( (xmin <= y[0]) && (y[0] <= xmax) &&
		   (ymin <= y[1]) && (y[1] <= ymax) &&
		   (zmin <= y[2]) && (y[2] <= zmax) ) {
		
		double k[6][6] = { {0.} };
		double ys[6][6] = { {0.} };
		
		for(int index = 0; index < 6; index++) {
			produce_new_y(y, ys, k, index);
			produce_new_k(ys, k, h, index, field, args);
		}
		
		double TE = 0.0; // Error 
		
		for(int i = 0; i < 6; i++) {
			double err = 0.0;
			for(int j = 0; j < 6; j++) err += CT[j]*k[j][i];
			if(fabs(err) > TE) TE = fabs(err);
		}
			
		if(TE <= atol || h == hmin) {
			for(int i = 0; i < 6; i++) {
				y[i] += CH[0]*k[0][i] + CH[1]*k[1][i] + CH[2]*k[2][i] + CH[3]*k[3][i] + CH[4]*k[4][i] + CH[5]*k[5][i];
				positions[N][i] = y[i];
			}
				
			N += 1;
			if(N==TRACING_BLOCK_SIZE) return N;
		}
		
		if (TE > atol / 10) h = fmax(fmin(0.9 * h * pow(atol / TE, 0.2), hmax), hmin);
		else if (TE < atol / 100) h = hmax;
	}
		
	return N;
}



//////////////////////////////// RADIAL RING POTENTIAL (DERIVATIVES)


double dr1_potential_radial_ring(double r_0, double z_0, double r, double z, void *_) {
	
	if (fabs(r_0) < MIN_DISTANCE_AXIS) return 0.0; // Prevent stepping into singularity
	
    double s = norm_2d(z-z_0, r+r_0);
    double s1 = (r_0 + r) / s;
    double t = 4.0 * r * r_0 / pow(s, 2);
    double A = ellipe(t);
    double B = ellipk(t);
    double ellipe_term = -(2.0 * r * r_0 * s1 - r * s) / (2.0 * r_0 * pow(s, 2) - 8.0 * pow(r_0, 2) * r);
    double ellipk_term = -r / (2.0 * r_0 * s);
    return A * ellipe_term + B * ellipk_term;
}


double potential_radial_ring(double r_0, double z_0, double r, double z, void *_) {
    double rz2 = pow(r + r_0, 2) + pow(z - z_0, 2);
    double t = 4.0 * r * r_0 / rz2;
    return ellipk(t) * r / sqrt(rz2);
}

double dz1_potential_radial_ring(double r_0, double z_0, double r, double z, void *_) {
    double rz2 = pow(r + r_0, 2) + pow(z - z_0, 2);
    double t = 4.0 * r * r_0 / rz2;
    double numerator = r * (z - z_0) * ellipe(t);
    double denominator = ((pow(z - z_0, 2) + pow(r - r_0, 2)) * sqrt(rz2));
    return numerator / denominator;
}

double
axial_potential_radial_ring(double r0, double z0, double r, double z, void* _) {
	double D0 = 1/norm_2d(z0-z, r);
	return M_PI*r/2 * D0;
}

double
dz_axial_potential_radial_ring(double r0, double z0, double r, double z, void* _) {
	double R = norm_2d(z0-z, r);
	double D1 = -(z0-z)/pow(R,3);
	return M_PI*r/2 * D1;
}

double
dnext_axial_potential_radial_ring(double r0, double z0, double r, double z, void* args_p) {
	struct {double *derivs; int n;} *args = args_p;
		
	double *derivs = args->derivs;
	int n = args->n;
		
	double R = norm_2d(z0-z, r);
		
	double Dnext = -1/pow(R,2) * ((2*n + 1)*(z0 - z)*derivs[1] + pow(n,2)*derivs[0]);
    return M_PI*r/2 * Dnext;
}


void
axial_derivatives_radial_ring(double* derivs_p, double *lines_p, double charges[], size_t N_lines, double z[], size_t N_z) {

	double (*derivs)[9] = (double (*)[9]) derivs_p;	
	double (*lines)[2][3] = (double (*)[2][3]) lines_p;

	for(int i = 0; i < N_z; i++) {
		for(int j = 0; j < N_lines; j++) {
			double *v1 = &lines[j][0][0];
			double *v2 = &lines[j][1][0];
				
			double target[2] = {0.0, z[i]};
			double derivs_line[9] = {0.};
			
			derivs_line[0] = line_integral(target, v1, v2, axial_potential_radial_ring, NULL);
			derivs_line[1] = line_integral(target, v1, v2, dz_axial_potential_radial_ring, NULL);
			
			for(int k = 2; k < 9; k++) {
				struct {double *derivs; int n;} args = {&derivs_line[k-2], k-1};
				derivs_line[k] = line_integral(target, v1, v2, dnext_axial_potential_radial_ring, &args);
			}

			for(int k = 0; k < 9; k++) derivs[i][k] += charges[j]*derivs_line[k];
		}
	}
}

//////////////////////////////// RADIAL SYMMETRY POTENTIAL EVALUATION

double
potential_radial(double point[3], double *vertices_p, double *charges, size_t N_vertices) {

	double (*vertices)[2][3] = (double (*)[2][3]) vertices_p;	

	double sum_ = 0.0;
	
	for(int i = 0; i < N_vertices; i++) {
		sum_ += charges[i] * line_integral(point, vertices[i][0], vertices[i][1], potential_radial_ring, NULL);
	}

	return sum_;
}



//////////////////////////////// RADIAL SYMMETRY FIELD EVALUATION

double
field_dot_normal_radial(double r0, double z0, double r, double z, void* normal_p) {
	
	double Er = -dr1_potential_radial_ring(r0, z0, r, z, NULL);
	double Ez = -dz1_potential_radial_ring(r0, z0, r, z, NULL);
	
	double *normal = (double *)normal_p;
		
	return normal[0]*Er + normal[1]*Ez;

}

void
field_radial(double point[3], double result[3], double *vertices_p, double *charges, size_t N_vertices) {

	double (*vertices)[2][3] = (double (*)[2][3]) vertices_p;	
	double Ex = 0.0, Ey = 0.0;
	
	for(int i = 0; i < N_vertices; i++) {
		Ex -= charges[i] * line_integral(point, vertices[i][0], vertices[i][1], dr1_potential_radial_ring, NULL);
		Ey -= charges[i] * line_integral(point, vertices[i][0], vertices[i][1], dz1_potential_radial_ring, NULL);
	}

	result[0] = Ex;
	result[1] = Ey;
	result[2] = 0.0;
}

struct field_evaluation_args {
	double *vertices;
	double *charges;
	size_t N_vertices;
};

void
field_radial_traceable(double point[3], double result[3], void *args_p) {

	struct field_evaluation_args *args = (struct field_evaluation_args*)args_p;
	field_radial(point, result, args->vertices, args->charges, args->N_vertices);
}

size_t
trace_particle_radial(double *pos_array, double bounds[3][2], double atol,
	double *vertices, double *charges, size_t N_vertices) {

	struct field_evaluation_args args = { vertices, charges, N_vertices };
				
	return trace_particle( pos_array, field_radial_traceable, bounds, atol, (void*) &args);
}

void
field_radial_derivs(double point[3], double field[3], double *z_inter, double *coeff_p, size_t N_z) {
	
	double (*coeff)[DERIVS_MAX_2D][4] = (double (*)[DERIVS_MAX_2D][4]) coeff_p;
	
	double r = point[0], z = point[1];
	double z0 = z_inter[0], zlast = z_inter[N_z-1];
	
	if(!(z0 < z && z < zlast)) {
		field[0] = 0.0, field[1] = 0.0;
		return;
	}

	double dz = z_inter[1] - z_inter[0];
	int index = (int) ( (z-z0)/dz );
	double diffz = z - z_inter[index];
		
	double (*C)[4] = &coeff[index][0];
		
	double derivs[DERIVS_MAX_2D];

	for(int i = 0; i < DERIVS_MAX_2D; i++)
		derivs[i] = C[i][0]*pow(diffz, 3) + C[i][1]*pow(diffz, 2) + C[i][2]*diffz + C[i][3];
		
	field[0] = r/2*(derivs[2] - pow(r,2)/8*derivs[4] + pow(r,4)/192*derivs[6] - pow(r,6)/9216*derivs[8]);
	field[1] = -derivs[1] + pow(r,2)/4*derivs[3] - pow(r,4)/64*derivs[5] + pow(r,6)/2304*derivs[7];
}

struct field_derivs_args {
	double *z_interpolation;
	double *axial_coefficients;
	size_t N_z;
};

void
field_radial_derivs_traceable(double point[3], double field[3], void *args_p) {
	struct field_derivs_args *args = (struct field_derivs_args*) args_p;
	field_radial_derivs(point, field, args->z_interpolation, args->axial_coefficients, args->N_z);
}

size_t
trace_particle_radial_derivs(double *pos_array, double bounds[3][2], double atol,
	double *z_interpolation, double *axial_coefficients, size_t N_z) {

	struct field_derivs_args args = { z_interpolation, axial_coefficients, N_z };
		
	return trace_particle( pos_array, field_radial_derivs_traceable, bounds, atol, (void*) &args);
}


//////////////////////////////// 3D POINT POTENTIAL (DERIVATIVES)

double dx1_potential_3d_point(double x0, double y0, double z0, double x, double y, double z, void *_) {
	double r = norm_3d(x-x0, y-y0, z-z0);
    return (x-x0)/(4*pow(r, 3));
}

double dy1_potential_3d_point(double x0, double y0, double z0, double x, double y, double z, void *_) {
	double r = norm_3d(x-x0, y-y0, z-z0);
    return (y-y0)/(4*pow(r, 3));
}

double dz1_potential_3d_point(double x0, double y0, double z0, double x, double y, double z, void *_) {
	double r = norm_3d(x-x0, y-y0, z-z0);
    return (z-z0)/(4*pow(r, 3));
}

double potential_3d_point(double x0, double y0, double z0, double x, double y, double z, void *_) {
	double r = norm_3d(x-x0, y-y0, z-z0);
    return 1/(4*r);
}

void
axial_coefficients_3d(double *vertices_p, double *charges, size_t N_v,
	double *zs, double *output_coeffs_p, size_t N_z,
	double *thetas, double *theta_coeffs_p, size_t N_t) {
	
	double (*vertices)[3][3] = (double (*)[3][3]) vertices_p;
	double (*theta_coeffs)[NU_MAX][M_MAX][4] = (double (*)[NU_MAX][M_MAX][4]) theta_coeffs_p;
	double (*output_coeffs)[2][NU_MAX][M_MAX] = (double (*)[2][NU_MAX][M_MAX]) output_coeffs_p;

	double theta0 = thetas[0];
	double dtheta = thetas[1] - thetas[0];
	
	for(int h = 0; h < N_v; h++) {

		double v1x = vertices[h][0][0], v1y = vertices[h][0][1], v1z = vertices[h][0][2];
		double v2x = vertices[h][1][0], v2y = vertices[h][1][1], v2z = vertices[h][1][2];
		double v3x = vertices[h][2][0], v3y = vertices[h][2][1], v3z = vertices[h][2][2];
			
		double area = 0.5*sqrt(pow((v2y-v1y)*(v3z-v1z)-(v2z-v1z)*(v3y-v1y), 2) + pow((v2z-v1z)*(v3x-v1x)-(v2x-v1x)*(v3z-v1z), 2) + pow((v2x-v1x)*(v3y-v1y)-(v2y-v1y)*(v3x-v1x), 2));
		
        for (int i=0; i < N_z; i++) 
		for (int k=0; k < N_TRIANGLE_QUAD; k++) {
			double b1_ = QUAD_B1[k];
			double b2_ = QUAD_B2[k];
			double w = QUAD_WEIGHTS[k];

			double x = v1x + b1_*(v2x-v1x) + b2_*(v3x-v1x);
			double y = v1y + b1_*(v2y-v1y) + b2_*(v3y-v1y);
			double z = v1z + b1_*(v2z-v1z) + b2_*(v3z-v1z);

			double r = norm_3d(x, y, z-zs[i]);
			double theta = atan2((z-zs[i]), norm_2d(x, y));
			double mu = atan2(y, x);

			int index = (int) ((theta-theta0)/dtheta);

			double t = theta-thetas[index];
			double (*C)[M_MAX][4] = &theta_coeffs[index][0];
				
			for (int nu=0; nu < NU_MAX; nu++)
			for (int m=0; m < M_MAX; m++) {
				double base = pow(t, 3)*C[nu][m][0] + pow(t, 2)*C[nu][m][1] + t*C[nu][m][2] + C[nu][m][3];
				double r_dependence = pow(r, -2*nu - m - 1);
					
				output_coeffs[i][0][nu][m] += charges[h]*area*w*base*cos(m*mu)*r_dependence;
				output_coeffs[i][1][nu][m] += charges[h]*area*w*base*sin(m*mu)*r_dependence;
			}
		}
	}
}


//////////////////////////////// 3D POINT POTENTIAL EVALUATION

double
potential_3d(double point[3], double *vertices_p, double *charges, size_t N_vertices) {

	double (*vertices)[3][3] = (double (*)[3][3]) vertices_p;	

	double sum_ = 0.0;
	
	for(int i = 0; i < N_vertices; i++) {
		sum_ += charges[i] * triangle_integral(point, vertices[i][0], vertices[i][1], vertices[i][2], potential_3d_point, NULL);
	}
	
	return sum_;
}

double
potential_3d_derivs(double point[3], double *zs, double *coeffs_p, size_t N_z) {

	double (*coeffs)[2][NU_MAX][M_MAX][4] = (double (*)[2][NU_MAX][M_MAX][4]) coeffs_p;
	
	double xp = point[0], yp = point[1], zp = point[2];

	if (!(zs[0] < zp && zp < zs[N_z-1])) return 0.0;

	double dz = zs[1] - zs[0];
	int index = (int) ((zp-zs[0])/dz);
	
	double z_ = zp - zs[index];

	double A[NU_MAX][M_MAX], B[NU_MAX][M_MAX];
	double (*C)[NU_MAX][M_MAX][4] = &coeffs[index][0];
		
	for (int nu=0; nu < NU_MAX; nu++)
	for (int m=0; m < M_MAX; m++) {
		A[nu][m] = pow(z_, 3)*C[0][nu][m][0] + pow(z_, 2)*C[0][nu][m][1] + z_*C[0][nu][m][2] + C[0][nu][m][3];
		B[nu][m] = pow(z_, 3)*C[1][nu][m][0] + pow(z_, 2)*C[1][nu][m][1] + z_*C[1][nu][m][2] + C[1][nu][m][3];
	}

	double r = norm_2d(xp, yp);
	double phi = atan2(yp, xp);
	
	double sum_ = 0.0;
	
	for (int nu=0; nu < NU_MAX; nu++)
	for (int m=0; m < M_MAX; m++)
		sum_ += (A[nu][m]*cos(m*phi) + B[nu][m]*sin(m*phi))*pow(r, (m+2*nu));
	
	return sum_;
}

//////////////////////////////// 3D POINT FIELD EVALUATION

double
field_dot_normal_3d(double x0, double y0, double z0, double x, double y, double z, void* normal_p) {
	
	double Ex = -dx1_potential_3d_point(x0, y0, z0, x, y, z, NULL);
	double Ey = -dy1_potential_3d_point(x0, y0, z0, x, y, z, NULL);
	double Ez = -dz1_potential_3d_point(x0, y0, z0, x, y, z, NULL);
	
	double *normal = (double *)normal_p;
	
    return normal[0]*Ex + normal[1]*Ey + normal[2]*Ez;
}


void
field_3d(double point[3], double result[3], double *vertices_p, double *charges, size_t N_vertices) {
	
		double (*vertices)[3][3] = (double (*)[3][3]) vertices_p;
		
		double Ex = 0.0, Ey = 0.0, Ez = 0.0;
		
		for(int i = 0; i < N_vertices; i++) {
			
			double *v1, *v2, *v3;
			v1 = &vertices[i][0][0], v2 = &vertices[i][1][0], v3 = &vertices[i][2][0];
			
			Ex -= charges[i]*triangle_integral(point, v1, v2, v3, dx1_potential_3d_point, NULL);
			Ey -= charges[i]*triangle_integral(point, v1, v2, v3, dy1_potential_3d_point, NULL);
			Ez -= charges[i]*triangle_integral(point, v1, v2, v3, dz1_potential_3d_point, NULL);
		} 

		result[0] = Ex;
		result[1] = Ey;
		result[2] = Ez;
}

void
field_3d_traceable(double point[3], double result[3], void *args_p) {

	struct field_evaluation_args *args = (struct field_evaluation_args*)args_p;
	field_3d(point, result, args->vertices, args->charges, args->N_vertices);
}

size_t
trace_particle_3d(double *pos_array, double bounds[3][2], double atol,
	double *vertices, double *charges, size_t N_vertices) {

	struct field_evaluation_args args = { vertices, charges, N_vertices };
				
	return trace_particle( pos_array, field_3d_traceable, bounds, atol, (void*) &args);
}

void
field_3d_derivs(double point[3], double field[3], double *zs, double *coeffs_p, size_t N_z) {
	
	double (*coeffs)[2][NU_MAX][M_MAX][4] = (double (*)[2][NU_MAX][M_MAX][4]) coeffs_p;

	double xp = point[0], yp = point[1], zp = point[2];

	field[0] = 0.0, field[1] = 0.0, field[2] = 0.0;
	
	if (!(zs[0] < zp && zp < zs[N_z-1])) return;
		
	double dz = zs[1] - zs[0];
	int index = (int) ((zp-zs[0])/dz);
	
	double z_ = zp - zs[index];

	double A[NU_MAX][M_MAX], B[NU_MAX][M_MAX];
	double Adiff[NU_MAX][M_MAX], Bdiff[NU_MAX][M_MAX];
	
	double (*C)[NU_MAX][M_MAX][4] = &coeffs[index][0];
		
	for (int nu=0; nu < NU_MAX; nu++)
	for (int m=0; m < M_MAX; m++) {
		A[nu][m] = pow(z_, 3)*C[0][nu][m][0] + pow(z_, 2)*C[0][nu][m][1] + z_*C[0][nu][m][2] + C[0][nu][m][3];
		B[nu][m] = pow(z_, 3)*C[1][nu][m][0] + pow(z_, 2)*C[1][nu][m][1] + z_*C[1][nu][m][2] + C[1][nu][m][3];
		
		Adiff[nu][m] = 3*pow(z_, 2)*C[0][nu][m][0] + 2*z_*C[0][nu][m][1]+ C[0][nu][m][2];
		Bdiff[nu][m] = 3*pow(z_, 2)*C[1][nu][m][0] + 2*z_*C[1][nu][m][1]+ C[1][nu][m][2];
	}
		
	double r = norm_2d(xp, yp);
	double phi = atan2(yp, xp);
	
	if(r < MIN_DISTANCE_AXIS) {
		field[0] = -A[0][1];
		field[1] = -B[0][1];
		field[2] = -Adiff[0][0];
		return;
	}
	
	
	for (int nu=0; nu < NU_MAX; nu++)
	for (int m=0; m < M_MAX; m++) {
		int exp = 2*nu + m;

		double diff_r = (A[nu][m]*cos(m*phi) + B[nu][m]*sin(m*phi)) * exp*pow(r, exp-1);
		double diff_theta = m*(-A[nu][m]*sin(m*phi) + B[nu][m]*cos(m*phi)) * pow(r, exp);
		
		field[0] -= diff_r * xp/r + diff_theta * -yp/pow(r,2);
		field[1] -= diff_r * yp/r + diff_theta * xp/pow(r,2);
		field[2] -= (Adiff[nu][m]*cos(m*phi) + Bdiff[nu][m]*sin(m*phi)) * pow(r, exp);
	}
}

void
field_3d_derivs_traceable(double point[3], double field[3], void *args_p) {
	struct field_derivs_args *args = (struct field_derivs_args*) args_p;
	field_3d_derivs(point, field, args->z_interpolation, args->axial_coefficients, args->N_z);
}

size_t
trace_particle_3d_derivs(double *pos_array, double bounds[3][2], double atol,
	double *z_interpolation, double *axial_coefficients, size_t N_z) {

	struct field_derivs_args args = { z_interpolation, axial_coefficients, N_z };
	
	return trace_particle( pos_array, field_3d_derivs_traceable, bounds, atol, (void*) &args);
}


//////////////////////////////// SOLVER

enum ExcitationType{
    VOLTAGE_FIXED = 1,
    VOLTAGE_FUN = 2,
    DIELECTRIC = 3,
    FLOATING_CONDUCTOR = 4};

void fill_matrix_radial(double* matrix_p, 
                        double* line_points_p, 
                        int* excitation_types, 
                        double* excitation_values, 
						size_t N_lines,
                        int lines_range_start, 
                        int lines_range_end) {
    
	assert(lines_range_start < N_lines && lines_range_end < N_lines);

	double (*matrix)[N_lines] = (double (*)[N_lines]) matrix_p;
	double (*line_points)[2][3] = (double (*)[2][3]) line_points_p;
		
    for (int i = lines_range_start; i <= lines_range_end; i++) {
		double *p1 = &line_points[i][0][0];
		double *p2 = &line_points[i][1][0];
		
		double target[2] = {(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2};
        enum ExcitationType type_ = excitation_types[i];
		 
        if (type_ == VOLTAGE_FIXED || type_ == VOLTAGE_FUN || type_ == FLOATING_CONDUCTOR) {
            for (int j = 0; j < N_lines; j++) {
                double *v1 = &line_points[j][0][0];
                double *v2 = &line_points[j][1][0];
                matrix[i][j] = line_integral(target, v1, v2, potential_radial_ring, NULL);
            }
        } 
        else if (type_ == DIELECTRIC) {
            double normal[2];
            normal_2d(p1, p2, normal);
            double K = excitation_values[i];
            
            for (int j = 0; j < N_lines; j++) {
				double *v1 = &line_points[j][0][0];
                double *v2 = &line_points[j][1][0];
				// This factor is hard to derive. It takes into account that the field
                // calculated at the edge of the dielectric is basically the average of the
                // field at either side of the surface of the dielecric (the field makes a jump).
                double factor = (2*K - 2) / (M_PI*(1 + K));
                matrix[i][j] = factor * line_integral(target, v1, v2, field_dot_normal_radial, normal);
                 
				// When working with dielectrics, the constraint is that
				// the electric field normal must sum to the surface charge.
				// The constraint is satisfied by subtracting 1.0 from
				// the diagonal of the matrix.
                if (i == j) matrix[i][j] -= 1.0;
            }
        }
        else {
            printf("ExcitationType unknown");
            exit(1);
        }
    }
}

void fill_matrix_3d(double* matrix_p, 
                    double* triangle_points_p, 
                    int* excitation_types, 
                    double* excitation_values, 
					size_t N_lines,
                    int lines_range_start, 
                    int lines_range_end) {
    
	assert(lines_range_start < N_lines && lines_range_end < N_lines);
	
	double (*matrix)[N_lines] = (double (*)[N_lines]) matrix_p;
	double (*triangle_points)[3][3] = (double (*)[3][3]) triangle_points_p;
		
    for (int i = lines_range_start; i <= lines_range_end; i++) {
		double *p1 = &triangle_points[i][0][0];
		double *p2 = &triangle_points[i][1][0];
		double *p3 = &triangle_points[i][2][0];
		double target[3] = {(p1[0] + p2[0] + p3[0])/3, (p1[1] + p2[1] + p3[1])/3, (p1[2] + p2[2] + p3[2])/3};
        enum ExcitationType type_ = excitation_types[i];
		 
        if (type_ == VOLTAGE_FIXED || type_ == VOLTAGE_FUN || type_ == FLOATING_CONDUCTOR) {
            for (int j = 0; j < N_lines; j++) {
                double *v1 = &triangle_points[j][0][0];
                double *v2 = &triangle_points[j][1][0];
                double *v3 = &triangle_points[j][2][0];
                matrix[i][j] = triangle_integral(target, v1, v2, v3, potential_3d_point, NULL);
            }
        } 
        else if (type_ == DIELECTRIC) {
            double normal[3];
            normal_3d(p1, p2, p3, normal);
            double K = excitation_values[i];
            
            for (int j = 0; j < N_lines; j++) {
				double *v1 = &triangle_points[j][0][0];
                double *v2 = &triangle_points[j][1][0];
                double *v3 = &triangle_points[j][2][0];
				// See comments in 'fill_matrix_2d'.
                double factor = (2*K - 2) / (M_PI*(1 + K));
                matrix[i][j] = factor * triangle_integral(target, v1, v2, v3, field_dot_normal_3d, normal);
				 
                if (i == j) matrix[i][j] -= 1.0;
            }
        }
        else {
            printf("ExcitationType unknown");
            exit(1);
        }
    }
}



