# -*- coding: UTF-8 -*-
import math
import sys
import itertools
import numpy as np
from numba import prange,jit
import scipy.spatial as spatial	
import time

#Avoid number error warnings
import warnings
warnings.filterwarnings("ignore")


"""
sterics

Computes steric data: L, Bmin, Bmax, Buried Volume
"""


@jit
def parallel_grid_scan(xy_grid, angle):
	"""angular sweep over grid points to find Bmin"""
	rmax = 0.0
	for i in prange(len(xy_grid)):
		r = xy_grid[i][0]*math.cos(angle)+xy_grid[i][1]*math.sin(angle)
		if r > rmax:
				rmax = r
	return rmax


def grid_round(x, spacing):
	"""Rounds distances into discrete numbers of grid intervals"""
	n = 1 / spacing
	return(round(x*n)/n)


def max_dim(coords, radii, options,resize=False):
	"""Establishes the smallest cuboid that contains all of the molecule, 
	if volume is requested, make sure sphere fits fully inside space"""
	spacing = options.grid
	[x_min, x_max, y_min, y_max, z_min, z_max] = np.zeros(6)
	
	#expand grid to fit sphere so we can measure buried volume accurately
	if resize:
		ex_radius = options.radius + options.radius * 0.1 #expanded radius, make sure our full sphere fits in our grid
		x_max = ex_radius
		y_max = ex_radius
		z_max = ex_radius
		x_min = -ex_radius
		y_min = -ex_radius
		z_min = -ex_radius
	
	for n, coord in enumerate(coords):
		[x_plus,y_plus,z_plus] = coord + np.array([radii[n], radii[n], radii[n]])
		[x_minus,y_minus,z_minus] = coord - np.array([radii[n], radii[n], radii[n]])
		if x_plus >= x_max: x_max = grid_round(x_plus, spacing) + spacing
		if y_plus >= y_max: y_max = grid_round(y_plus, spacing) + spacing
		if z_plus >= z_max: z_max = grid_round(z_plus, spacing) + spacing
		if x_minus <= x_min: x_min = grid_round(x_minus, spacing) - spacing
		if y_minus <= y_min: y_min = grid_round(y_minus, spacing) - spacing
		if z_minus <= z_min: z_min = grid_round(z_minus, spacing) - spacing

	# largest dimension along any axis
	max_dim = max(x_max, y_max, z_max, abs(x_min), abs(y_min), abs(z_min))
	if options.verbose: print("\n   Molecule is bounded by the region X:[{:6.3f} to{:6.3f}] Y:[{:6.3f} to{:6.3f}] Z:[{:6.3f} to{:6.3f}]".format(x_min, x_max, y_min, y_max, z_min, z_max))

	# compute cubic volume containing molecule and estimate the number of grid points based on grid spacing and volume size
	cubic_volume = (2 * max_dim) ** 3
	n_points = int(cubic_volume / (spacing ** 3))
	return [x_min, x_max, y_min, y_max, z_min, z_max, max_dim]


def occupied(grid, coords, radii, origin, options):
	"""Uses atomic coordinates and VDW radii to establish which grid voxels are occupied"""
	spacing = options.grid
	if options.verbose ==True: print("\n   Using a Cartesian grid-spacing of {:5.4f} Angstrom.".format(spacing))
	if options.verbose ==True: print("   There are {} grid points.".format(len(grid)))

	idx, point_tree  = [], spatial.cKDTree(grid)
	for n, coord in enumerate(coords):
		center = coord + origin
		idx.append(point_tree.query_ball_point(center, radii[n]))
	# construct a list of indices of the grid array that are occupied
	jdx = [y for x in idx for y in x]
	# removes duplicates since a voxel can only be occupied once
	jdx = list(set(jdx))
	if options.verbose: print("   There are {} occupied grid points.".format(len(jdx)))
	if options.verbose: print("   Molecular volume is {:5.4f} Ang^3".format(len(jdx) * spacing ** 3))
	
	#visualize grid points quickly
	# import pptk
	# u = pptk.viewer(grid)
	# v = pptk.viewer(grid[jdx])
	
	return grid[jdx]


def occupied_dens(grid, dens, options):
	"""Uses density cube to establish which grid voxels are occupied (i.e. density is above some isoval, by default 0.002)"""
	spacing, isoval = options.grid, options.isoval
	cube, list = (spacing / 0.529177249) ** 3, []
	if options.verbose: print("\n   Using a Cartesian grid-spacing of {:5.4f} Angstrom".format(spacing))

	for n, density in enumerate(dens):
		if density > isoval: list.append(n)
	if options.verbose: print("   Molecular volume is {:5.4f} Ang^3".format(len(list) * spacing ** 3))
	return grid[list]


def resize_grid(x_max,y_max,z_max,x_min,y_min,z_min,options,mol):
	"""Resize the grid to accomodate the sphere for volume calculations"""
	if x_max < options.radius+options.radius*0.1: 
		x_orig = x_max
		x_max = options.radius+options.radius*0.1
		diff = abs(x_max - x_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.xdim = mol.xdim + int(new_points)
	if y_max < options.radius+options.radius*0.1: 
		y_orig = y_max
		y_max = options.radius+options.radius*0.1
		diff = abs(y_max - y_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.ydim = mol.ydim + int(new_points)
	if z_max < options.radius+options.radius*0.1: 
		z_orig = z_max
		z_max = options.radius+options.radius*0.1
		diff = abs(z_max - z_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.zdim = mol.zdim + int(new_points)
	if x_min > -(options.radius+options.radius*0.1): 
		x_orig = x_min
		x_min = -(options.radius+options.radius*0.1)
		diff = abs(x_min - x_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.xdim = mol.xdim + int(new_points)
	if y_min > -(options.radius+options.radius*0.1): 
		y_orig = y_min
		y_min = -(options.radius+options.radius*0.1)
		diff = abs(y_min - y_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.ydim = mol.ydim + int(new_points)
	if z_min > -(options.radius+options.radius*0.1): 
		z_orig = z_min
		z_min = -(options.radius+options.radius*0.1)
		diff = abs(z_min - z_orig)
		diff_round = grid_round(diff,options.grid)
		new_points = diff_round / options.grid
		mol.zdim = mol.zdim + int(new_points)
	#expand grid with empty points to fit 
	x_vals = np.linspace(x_min, x_max, mol.xdim)
	y_vals = np.linspace(y_min, y_max, mol.ydim)
	z_vals = np.linspace(z_min, z_max, mol.zdim)
	grid = np.array(list(itertools.product(x_vals, y_vals, z_vals)))
	
	return grid
	

def get_classic_sterimol(coords, radii, atoms, spec_atom_1, spec_atom_2):
	"""Uses standard Verloop definitions and VDW spheres to define L, B1 and B5"""
	L, Bmax, Bmin, xmax, ymax, cyl, rad_hist_hy,rad_hist_rw, x_hist_rw, y_hist_rw,x_hist_hy, y_hist_hy  = 0.0, 0.0, 0.0, 0.0, 0.0, [], [], [], [], [], [], []
	for n, coord in enumerate(coords):
		# L parameter - this is not actually the total length, but the largest distance from the basal XY-plane. Any atoms pointing below this plane (i.e. in the opposite direction) are not counted.
		# Verloop's original definition does include the VDW of the base atom, which is totally weird and is not done here. There will be a systematic difference vs. literature
		length = abs(coord[2]) + radii[n]
		if length > L: L = length

		# B5 parameter
		x,y,z = coord
		radius = np.hypot(x,y) + radii[n]
		if x != 0.0 and y != 0.0:
			x_hist_hy.append(x)
			y_hist_hy.append(y)
			rad_hist_hy.append(radius)
		rad_hist_rw.append(radii[n])
		x_hist_rw.append(x)
		y_hist_rw.append(y)
		if radius > Bmax:
			Bmax, xmax, ymax = radius, x, y
			# don't actually need this for Sterimol. It's used to draw a vector direction along B5 to be displayed in PyMol
			theta = np.arctan(y/x)
			if x < 0: theta += math.pi
			if x != 0. and y!= 0.:
				x_disp, y_disp = radii[n] * math.cos(theta), radii[n] * math.sin(theta)
			elif x == 0. and y != 0.:
				x_disp, y_disp = 0.0, radii[n] * math.sin(theta)
			elif x != 0. and y == 0.:
				x_disp, y_disp = radii[n]* math.cos(theta), 0.0
			else:
				x_disp, y_disp = radii[n], 0.0
			xmax += x_disp; ymax += y_disp

	# A nice PyMol cylinder object points along the B5 direction with the appopriate magnitude
	cyl.append("   CYLINDER, 0., 0., {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0,".format(0.0, xmax, ymax, 0.0, 0.1))

	# Drop the Z coordinates and calculate B1
	xycoords = [(x,y) for x,y,z in coords]
	#increments = 6000 # this goes around in 0.06 degree intervals
	increments = 361 # this goes around in 1 degree intervals
	angles = np.linspace(-math.pi, -math.pi + 2 * math.pi, increments) # sweep full circle
	Bmin = sys.float_info.max
	xmin,ymin = 0,0
	for angle in angles:
		angle_val = 0.0
		for i in range(len(xycoords)):
			projection = (xycoords[i][0])*math.cos(angle) + (xycoords[i][1])*math.sin(angle)
			radius = projection + radii[i]

			if radius > angle_val:
				angle_val, x, y = radius, radius*math.cos(angle),radius*math.sin(angle)

		if Bmin > angle_val:
			Bmin,xmin,ymin = angle_val,x,y

	cyl.append("   CYLINDER, 0., 0., {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0,".format(0.0, xmin, ymin, 0.0, 0.1))
	return L, Bmax, Bmin, cyl


def get_cube_sterimol(occ_grid, R, spacing, strip_width):
	"""Uses grid occupancy to define Sterimol L, B1 and B5 parameters. If the grid-spacing is small enough this should be close to the
	conventional values above when the grid occupancy is based on VDW radii. The real advantage is that the isodensity surface can be used,
	which does not require VDW radii, and this also looks something a bit closer to a solvent-accessible surface than the sum-of-spheres.
	Also B1 can be defined in a physically more # meaningful way than the traditional approach. This method can take horizontal slices to
	evaluate these parameters along the L-axis, which is also a nightmare with the conventional definition."""
	
	L, Bmax, Bmin, xmax, ymax, zmax, xmin, ymin, cyl = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, []

	# this is a layer of the occupancy grid between Z-limits
	if strip_width != 0: xy_grid = np.array([(x,y,z) for x,y,z in occ_grid if abs(z) <= R + strip_width and abs(z) > R - strip_width])
	else: xy_grid = occ_grid

	if len(xy_grid) > 0:
		#radii = map(lambda x: math.sqrt(x[0]**2+x[1]**2), xy_grid)
		radii = [math.sqrt(x**2+y**2) for x,y,z in xy_grid]
		Bmax, imax = max(radii), np.argmax(radii)
		xmax, ymax, zmax = xy_grid[imax]
		#print(Bmax, math.sqrt(xmax**2+ymax**2))
		L = max(map(lambda x: x[2], xy_grid))

		# Go around in angle increments and record the farthest out point in each slice
		increments = 361
		angles = np.linspace(-math.pi, -math.pi+2*math.pi, increments) # sweep full circle

		Bmin = sys.float_info.max
		xmin,ymin = 0,0
		max_r, max_phi = [], []

		for angle in angles:
			rmax = parallel_grid_scan(xy_grid,angle)

			if rmax != 0.0: # by definition can't have zero radius
				max_r.append(rmax)
				max_phi.append(angle)

		if len(max_r) > 0:
			Bmin = min(max_r)
			xmin, ymin = Bmin * math.cos(max_phi[np.argmin(max_r)]), Bmin * math.sin(max_phi[np.argmin(max_r)])

	elif len(xy_grid) == 0:
		Bmin, xmin, ymin, Bmax, xmax, ymax, L = 0,0,0,0,0,0,0

	# A nice PyMol cylinder object points along the B5 & B1 directions with the appopriate magnitude.
	# In the event that several strips are being evaluated several B-vectors will be arranged along the L-axis.
	# If not a single vector will be shown in the basal plane
	if strip_width == 0.0:
		cyl.append("   CYLINDER, 0., 0., {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0,".format(0.0, xmin, ymin, 0.0, 0.1))
		cyl.append("   CYLINDER, 0., 0., {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0,".format(0.0, xmax, ymax, 0.0, 0.1))
	else:
		cyl.append("   CYLINDER, 0., 0., {:5.1f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 0.0, 1.0, 0.0,".format(R, xmin, ymin, R, 0.1))
		cyl.append("   CYLINDER, 0., 0., {:5.1f}, {:5.3f}, {:5.3f}, {:5.3f}, {:5.3f}, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0,".format(R, xmax, ymax, R, 0.1))
	return L, Bmax, Bmin, cyl


def buried_vol(occ_grid, all_grid, origin, R, spacing, strip_width, verbose):
	""" Read which grid points occupy sphere"""
	sphere = 4 / 3 * math.pi * R ** 3 #vol of sphere w/ radius R
	cube = spacing ** 3 # cube 
	vol_err = 100.
	old_err = sys.float_info.max
	old_volume = sys.float_info.max
	old_percent_buried_vol = sys.float_info.max
	while abs(vol_err) > 5.0:
		# Quick way to find all points in the grid within a sphere radius R
		point_tree = spatial.cKDTree(all_grid)
		n_voxel = len(point_tree.query_ball_point(origin, R))
		tot_vol = n_voxel * cube
		# Quick way to find all occupied points within the same spherical volume
		point_tree = spatial.cKDTree(occ_grid)
		n_occ = len(point_tree.query_ball_point(origin, R))
		occ_vol = n_occ * cube
		free_vol = tot_vol - occ_vol 
		percent_buried_vol = occ_vol / tot_vol * 100.0
		#vol_err = tot_vol/sphere * 100.0
		vol_err = abs(tot_vol-sphere)/sphere * 100.0
		
		if old_volume == tot_vol: #included max points
			percent_buried_vol = old_percent_buried_vol
			break
		elif old_err < vol_err: #error is minimized, ignore most recent update
			percent_buried_vol = old_percent_buried_vol
			vol_err = old_err
			break
		else:
			old_volume = tot_vol
			old_err = vol_err
			old_percent_buried_vol = percent_buried_vol
			R = R+R*.10
		if abs(vol_err) > 5.0 and verbose: 
			if verbose: print("   Volume error too large ({:3.2f}%) adding more points to volume calculation.".format(vol_err))
	
	# experimental - in addition to occupied spherical volume, this will compute
	# the percentage occupancy of a radial shell between two limits if a scan
	# along the L-axis is being performed
	if strip_width != 0.0:
		shell_vol = 4 / 3 * math.pi * ((R + 0.5 * strip_width) ** 3 - (R - 0.5 * strip_width) ** 3)
		point_tree = spatial.cKDTree(occ_grid)
		shell_occ = len(point_tree.query_ball_point(origin, R + 0.5 * strip_width)) - len(point_tree.query_ball_point(origin, R - 0.5 * strip_width))
		shell_occ_vol = shell_occ * cube
		percent_shell_vol = shell_occ_vol / shell_vol * 100.0
	else: percent_shell_vol = 0.0

	if verbose:
		print("   RADIUS: {:5.2f}, VFREE: {:7.2f}, VBURIED: {:7.2f}, VTOTAL: {:7.2f}, VEXACT: {:7.2f}, NVOXEL: {}, %V_Bur: {:7.2f}%,  Tot/Ex: {:7.2f}%".format(R, free_vol, occ_vol, tot_vol, sphere, n_voxel, percent_buried_vol, vol_err))
	
	if abs(vol_err) > 5.0:
		print("   WARNING! {:5.2f}% error in estimating the exact spherical volume. The grid spacing is probably too big in relation to the sphere volume".format(vol_err))
	
	return percent_buried_vol, percent_shell_vol