import numpy as np
import perturbations  as PB
import math
G    = 4.32275e-3       # (km/s)^2 pc/Msun
G_pc = G*1.05026504e-27 # (pc/s)^2 pc/Msun
kmtopc = 1.0/(3.086*10**13)
MNS  = 1.4 # Msun
RNS  = 10*kmtopc # pc
from scipy.interpolate import interp1d
from scipy.integrate import quad, cumtrapz
from scipy.special import erfi
from scipy.special import gamma as gamma_fun

#BJK: Corrections
#   - Neutron star radius set to 1.4 km -> Changed to 10 km
#   - Neutron star mass set to 1 M_sun -> Changed to 1.4 M_sun
#   - Angular dependence of signal not correct
#   - Density enhancement around neutron star now incorporated.
#   - Factor of GeV -> J missing in calculation of flux in muJy
    


##
##  NS distributions
##
#Fraction of bound NS's, roughly from Table 4 of https://arxiv.org/pdf/0908.3182.pdf
f_bound = 0.8
N_bulge = f_bound*6.0e8
N_disk = f_bound*4.0e8


def f_NFW(x):
    return np.log(1+x) - x/(1+x)

def density(mass, radius):
        return 3.*mass/(4.*np.pi*radius**3)

def del_density(mass, radius):
    return 3.*density(mass, radius)/radius

def MCradius(mass, density):
    return (3.*mass/(4.*np.pi*density))**(1./3.)

# Interpolation function for radius as a function of NFW density
#--------------------------------------------------------------
c = 100
x_list = np.geomspace(1e-5, 1e5, 1000) # x = r/R_max = r/(c r_s)
rho_list = 1/((c*x_list)*(1+c*x_list)**2)
x_of_rho_interp = interp1d(rho_list, x_list, bounds_error=False, fill_value = 0.0)
def x_of_rho(rho):
    x = x_of_rho_interp(rho)
    m1 = rho > np.max(rho_list)
    x[m1] = c**-1/(rho[m1])
    m2 = rho < np.min(rho_list)
    x[m2] = c**-1/(rho[m2])**(1/3)
    return x    
#--------------------------------------------------------------

#R_cyl is the cylindrical galactocentric distance
def nNS_bulge(R_cyl, Z):
    #Bulge distribution from McMillan, P.J. 2011, MNRAS, 414, 2446 1102.4340
    # R_cyl and Z are cylindrical coordinates in pc

    r0 = 75.             #pc ### This value has been changed from 750pc to 75pc
    rc = 2.1e3          #pc
    Nnorm = 1/90218880.  #pc^{-3} - normalising constant so that the distribution integrates to 1 over the whole volume
    rp2 = R_cyl**2 + 4*Z**2
    rp  = np.sqrt(rp2)
    return N_bulge*Nnorm*np.exp(-rp2/rc**2)/(1+rp/r0)**(1.8)

def nNS_disk(R_cyl, Z):
    #Lorimer profile, Eq. 6 of https://arxiv.org/pdf/1805.11097.pdf
    #Best fit parameters from Table 3 (Broken Power-Law)
    Rsun = 8.5e3 #We use R_sun = 8.5 kpc here for consistency with the fits in 1805.11097
    B = 3.91 
    C = 7.54
    Zs = 0.76e3 
    
    Norm = C**(B+2)/(4*np.pi*Rsun**2*Zs*np.exp(C)*gamma_fun(B+2))
    return N_disk*Norm*(R_cyl/Rsun)**B*np.exp(-C*(R_cyl-Rsun)/Rsun)*np.exp(-np.abs(Z)/Zs)

def nNS(R_cyl, Z):
    return nNS_bulge(R_cyl, Z) + nNS_disk(R_cyl, Z)


#Tabulate
nNS_sph_interp = None

def calcNS_sph():
    #Galactocentric, spherical R
    r_list = np.geomspace(1, 200e3, 10000)
    nr_list = 0.0*r_list

    for i, r in enumerate(r_list):
        Z_list = 0.99999*np.linspace(-r, r, 1001)
        R_list = np.sqrt(r**2 - Z_list**2)
        nr_list[i] = (0.5/r)*np.trapz(nNS(R_list, Z_list), Z_list)
    
    return interp1d(r_list, nr_list, bounds_error=False, fill_value=0.0)

#Galactocentric, spherical R
def nNS_sph(R_sph):
    global nNS_sph_interp
    if (nNS_sph_interp is None):
        nNS_sph_interp = calcNS_sph()
    
    return nNS_sph_interp(R_sph)


#Parallelised for Z
def dPdZ(R_sph, Z):
    ma = R_sph**2 > Z**2 #Mask for valid values
    R_cyl = np.sqrt(R_sph**2 - Z[ma]**2)
    
    result = 0.0*Z
    result[ma] = nNS(R_cyl, Z[ma])/(2*R_sph*nNS_sph(R_sph))
    #P(Z) = P(R_sph, Z)/P(R_sph) = (2 pi R_sph n(R_cyl, Z)/(4 pi R_sph^2 <n(R_sph)>))
    return result
#--------------------------------------------------------------

# Integrate over \phi in spherical coordinates
#def nNS_sph(R):
#    Nb = 6.0e8
#    ab = 0.6e3  #pc
#    n_bulge = Nb/(2.0*np.pi)*(ab/R)/(ab+R)**3
#
#    Nd = 4.0e8
#    sz = 1.0e3  #pc
#    ss = 5.0e3  #pc
#    n0 = Nd/(4.0*np.sqrt(2*np.pi)*sz*ss*R)
#    n_disc = n0*np.exp(-0.5*(R/ss)**2-0.5*(ss/sz)**2)
#    n_disc *= (erfi(ss/(np.sqrt(2)*sz)) + erfi((R*sz - ss**2)/(np.sqrt(2)*ss*sz)))
#    #n_disc = n0*2.0*np.exp(-0.5*(R/ss)**2)*np.sqrt(np.pi)*ss*sz
#    #n_disc = n_disc*math.erf(R*np.sqrt(ss**2 - sz**2/2.0)/ss/sz)
#    #n_disc = n_disc/(R*np.sqrt((2.0*ss)**2 - 2.0*sz**2))
#
#    return n_bulge + n_disc

#R here is the 'spherical' galactocentric distance
#def n_NS_total(R, Z):
#    Nb = 6.0e8
#    ab = 0.6e3
#    n_bulge = Nb/(2.0*np.pi)*(ab/R)/(ab+R)**3
#    Nd = 4.0e8
#    sz = 1.0e3
#    ss = 5.0e3
#    nd = Nd/(4.0*np.pi*sz*ss**2)
#    return n_bulge + nd*np.exp( -0.5*(R**2-Z**2)/ss**2 - (np.abs(Z)/sz))


## NFW profile for AMC distribution
def rhoNFW(R):
    rho0 =  1.4e7*1e-9 # Msun*pc^-3, see Table 1 in 1304.5127
    rs = 16.1e3      # pc
    aa = R/rs
    return rho0/aa/(1+aa)**2

## AMC distributions

#HMF which is vectorised...
def HMF(mass, mmin, mmax, gg):
    # Halo Mass Function 
    g1   = 1.-gg
    ff = g1*mass**g1/(mmax**g1-mmin**g1)
    ff[mass > mmax] = 0.
    ff[mass < mmin] = 0.
    return ff

# FIXME: What is the different between there. Remove...

@np.vectorize
def HMF_sc(mass, mmin, mmax, gg):
    # Halo Mass Function 
    g1   = 1.-gg
    ff = 0 # FIXME: Check whether changing this number affects anything
    if mass < mmax and mass > mmin:
        ff = g1*mass**g1/(mmax**g1-mmin**g1)
    return ff


def P_r_given_rho(R, rho, mmin, mmax, gg):
    mass = 4.*np.pi*rho*R**3/3.
    # print('made it here', HMF_sc(mass, mmin, mmax, gg), mass, mmin, mmax, gg)
    # quit()
    return 3.*mass/R*HMF_sc(mass, mmin, mmax, gg)/mass

##
## Cross-section
##

def sigma_grav(R_AMC):
    # The velocity dispersion is Maxwell-Boltzmann with dispersion sigma_u=290km/s
    # The cross-section is \pi(R^2)(1+sigma_G2/u^2) with sigma_G2 = 2GM/R
    # The velocity-averaged cross section is \sqrt(2/pi/sigma_u^2)(sigma_G +2sigma_u^2)
    sigma_G2 = 2.0*G*MNS/(RNS + R_AMC) # (km/s)**2
    sigma_u2 = 290.0**2  # (km/s)**2
    ## Returns the cross section*u in pc^3/s
    return (RNS**2 + R_AMC**2)*np.sqrt(2.0*np.pi/sigma_u2)*(sigma_G2 +2.0*sigma_u2)*kmtopc

def Vcirc(rho):
    rho0 =  1.4e7*1e-9 # Msun pc^-3, see Table 1 in 1304.5127
    rs   = 16.1e3      # pc
    Menc = 4*np.pi*rho0*rs**3*(np.log((rs+rho)/rs) - rho/(rs+rho))
    return np.sqrt(G_pc*Menc/rho) # pc/s

def MC_profile(delta, r):
    # r is in units of the axion MC
    # Return the density of axion MC in GeV/pc^3
    hbarc = 0.197e-13 # GeV*cm
    pc    = 3.086e18  # cm to pc
    rhoeq = 2.45036e-37*(pc/hbarc)**3  # GeV/pc^3
    rhoc  = 140.*(1. + delta)*delta**3*rhoeq
    return 0.25*rhoc/r**(9/4)

#def MC_profile_self(M, R, r):
#    ## r is in units of the axion MC radius
#    ## M is in units of M_Sun
#    ## R is in pc
#    ## Returns the density of axion MCs in GeV/pc^3
#    MSuninGeV = 1.115e57
#    rho0 = 1.3187e62 # Density of axion MC in GeV/pc^3
#    return 3.*M/(4.*np.pi*R**3)*MSuninGeV/r**(9/4)

def MC_profile_self(density, r):
    ## r is in units of the axion MC radius
    ## Returns the density of axion MCs in GeV/pc^3
    MSuninGeV = 1.115e57
    #Factor of 0.25 because density at surface is rho/4
    return 0.25*density*MSuninGeV/r**(9/4)
    
def MC_profile_NFW(density, r):
    c = 100
    MSuninGeV = 1.115e57
    rho_s = density*c**3/(3*f_NFW(c))
    return rho_s*MSuninGeV/(c*r*(1+c*r)**2)
    
    
def rc(theta, B0, P0, mGhz):
    ## code Eq.5 in 1804.03145
    ## Returns the conversion radius in pc
    rc0 = 7.25859e-12 # pc, equal to 224 km
    ft  = np.abs(3.*np.cos(theta)**2 - 1)
    return rc0*(RNS/(10*kmtopc))*(ft*B0/1.e14*1/P0/mGhz**2)**(1./3.)

def signal(theta, Bfld, Prd, density, fa, ut, s0, r, ret_bandwidth=False, profile = "PL"):
    # Returns the expected signal in microjansky
    cs          = 3.0e8     # speed of light in m/s
    pc          = 3.0860e16 # pc in m
    hbar        = 6.582e-16 # GeV/GHz
    hbarT       = 6.582e-25 # GeV s
    GaussToGeV2 = 1.953e-20 # GeV^2
    alpEM       = 1/137.036 # Fine-structure constant
    Lambda      = 0.0755    # confinment scale in GeV

    ma     = Lambda**2/fa   # axion mass in GeV
    maGHz        = ma/hbar   # axion mass in GHz
    ga = alpEM/(2.*np.pi*fa)*(2./3.)*(4. + 0.48)/1.48 # axion-photon coupling in GeV^-1
    BGeV = GaussToGeV2*Bfld # B field in GeV^2
    
    vrel0  = 1.e-3          # relative velocity in units of c
    vrel   = vrel0*cs/pc    # relative velocity in pc/s
    bandwidth0 = vrel0**2/(2.*np.pi)*maGHz*1.e9 # Bandwidth in Hz
    rcT   = rc(theta, Bfld, Prd, maGHz) # conversion radius in pc
    
    vc    = 0.544467*np.sqrt(RNS/rcT) # free-fall velocity at rc in units of c
    BWD   = bandwidth0*(ut/vrel)**2    # bandwidth in Hz
    
    if (profile == "PL"):
        rhoa  = MC_profile_self(density, r)
    elif (profile == "NFW"):
        rhoa = MC_profile_NFW(density, r)
        
    #BJK: I think this expression for the flux is wrong. Possibly? The angular dependence certainly looks odd.
    #Also, it looks like it doesn't correct for the enhancement of density at r_c?
    Flux  = np.pi/6.*ga**2*vc*(RNS/rcT)**3*BGeV**2*np.abs(3.*np.cos(theta)**2-1.)*(rhoa*RNS**3/ma)
    
    # 1.e32 is the conversion from SI to muJy. hbar converts from GeV to s^-1
    if ret_bandwidth:
        # GeV/m^2 -> 1e32
        # 1 muJy = 1e-32 J/m^2
        return Flux/(BWD*4.*np.pi*(s0*pc)**2*hbarT) * 1.e32, BWD
    else:
        return Flux/(BWD*4.*np.pi*(s0*pc)**2*hbarT) * 1.e32,

def signal_isotropic(Bfld, Prd, density, fa, ut, s0, r, ret_bandwidth=False, profile = "PL"):
    # Returns the expected signal in microjansky
    cs          = 3.0e8     # speed of light in m/s
    pc          = 3.0860e16 # pc in m
    hbar        = 6.582e-16 # GeV/GHz
    hbarT       = 6.582e-25 # GeV s
    GaussToGeV2 = 1.953e-20 # GeV^2
    alpEM       = 1/137.036 # Fine-structure constant
    Lambda      = 0.0755    # confinment scale in GeV
    GeV_to_J    = 1.602e-10

    ma     = Lambda**2/fa   # axion mass in GeV
    maGHz        = ma/hbar   # axion mass in GHz
    ga = alpEM/(2.*np.pi*fa)*(2./3.)*(4. + 0.48)/1.48 # axion-photon coupling in GeV^-1
    BGeV = GaussToGeV2*Bfld # B field in GeV^2

    #rcT   = rc(theta, Bfld, Prd, maHz) # conversion radius in pc    
    #Mean conversion radius: = 0.5 int_{-1}^{1} |3 x - 1|^{1/3} dx ~ 0.869
    #Fix theta = pi, to give |3 cos(theta) - 1|^{1/3} = 1 in the expression for r_c
    rcT_mean = 0.869*rc(np.pi, Bfld, Prd, maGHz) # *MEAN* conversion radius in pc 
    
    #What the hell is this?
    #vc    = 0.544467*np.sqrt(RNS/rcT_mean) # free-fall velocity at rc in units of c
    vc = np.sqrt(2*G_pc*MNS/rcT_mean)/(cs/pc) # free-fall velocity at *MEAN* rc in units of c

    BWD   = 1.0e3 + density*0.0 #Fix bandwidth to 1 kHz
    
    if (profile == "PL"):
        rhoa  = MC_profile_self(density, r)
    elif (profile == "NFW"):
        rhoa = MC_profile_NFW(density, r)
        
    #Enhanced density at r_c (obtained by conservation of flux)
    rho_rc = rhoa*np.sqrt(2*G_pc*MNS/rcT_mean)/ut
    #Correct angular dependence of B-field should be B^2(theta) ~ (3.*np.cos(theta)**2+1.)
    #See. Eq. 2 of https://arxiv.org/pdf/1811.01020.pdf. Taking the angular average we just
    #get a factor of 2: 0.5 int_{-1}^1 (3.*x**2+1.) dx = 2
    Flux  = 2*np.pi/6.*ga**2*vc*(RNS/rcT_mean)**3*BGeV**2*(rho_rc*RNS**3/ma)
    
    # 1.e32 is the conversion from SI to muJy. hbar converts from GeV to s^-1
    if ret_bandwidth:
        return Flux*GeV_to_J/(BWD*4.*np.pi*(s0*pc)**2*hbarT) * 1.e32, BWD
    else:
        return Flux*GeV_to_J/(BWD*4.*np.pi*(s0*pc)**2*hbarT) * 1.e32,


def n(rho, psi):
    # The AMC stars with a positions defined by rho in pc
    # Its angle out of the plane is given by psi
    rho0 =  1.4e7*1e-9 # Msun pc^-3, see Table 1 in 1304.5127
    rs   = 16.1e3      # pc
    Menc = 4*np.pi*rho0*rs**3*(np.log((rs+rho)/rs) - rho/(rs+rho))
    gravfactor = lambda t: np.sqrt(G_pc*(Menc)/rho**3)*t
    R   = lambda t: np.sqrt((np.cos(psi)*rho*np.cos(gravfactor(t)))**2 + (rho*np.sin(gravfactor(t)))**2)
    Z   = lambda t: np.sin(psi)*rho*np.cos(gravfactor(t))
    n_t = lambda t: nNS(R(t), Z(t))
    return n_t

def Ntotal(nfunc, Tage, sigmau):
    Ntfunc = lambda t: nfunc(t)*sigmau
    tlist  = np.linspace(0, Tage, 1000)
    return np.trapz(Ntfunc(tlist), x=tlist)

def Gamma(nfunc, Tage, sigmav ):
    Ntfunc = lambda t: nfunc(t)*sigmav
    tlist = np.geomspace(1, Tage, 1000)
    return np.trapz(Ntfunc(tlist), x=tlist)

def inverse_transform_sampling_log(function, x_range, nbins=1000, n_samples=1000):
    bins = np.geomspace(x_range[0], x_range[-1], num=nbins)
    pdf = function(np.delete(bins,-1) + np.diff(bins)/2)
    # Norm = np.sum(pdf*np.diff(bins))
    Norm = np.trapz(pdf, x=np.delete(bins,-1) + np.diff(bins)/2)
    pdf /= Norm
    # cum_values = np.zeros(bins.shape)
    cum_values = cumtrapz(pdf, x=np.delete(bins,-1) + np.diff(bins)/2, initial=0.0)
    inv_cdf = interp1d(cum_values, np.delete(bins,-1) + np.diff(bins)/2)
    r = np.random.rand(n_samples)
    return inv_cdf(r)

def inverse_transform_sampling(function, x_range, nbins=1000, n_samples=1000):
    bins = np.linspace(x_range[0], x_range[-1], num=nbins)
    pdf = function(np.delete(bins,-1) + np.diff(bins)/2)
    Norm = np.trapz(pdf, x=np.delete(bins,-1) + np.diff(bins)/2)
    pdf /= Norm
    # cum_values = np.zeros(bins.shape)
    cum_values = cumtrapz(pdf, x=np.delete(bins,-1) + np.diff(bins)/2, initial=0.0)
    inv_cdf = interp1d(cum_values, np.delete(bins,-1) + np.diff(bins)/2)
    r = np.random.rand(n_samples)
    return inv_cdf(r)

def dPdR(bmax, Nsamples=1000):
    # b in km
    # bmin should be the minimum impact encounter
    brange = np.array([b0,bmax])
    DF_b = lambda x: 2*b/(bmax**2 - b0**2)
    blist = inverse_transform_sampling(DF_b, brange, n_samples=Nsamples)
    return blist

def Elist(Vlist, blist, Mp, Ms, Rrms2):
    # V in km s^-1
    # M in Msun
    return 4*(G**2)*(Mp**2)*Ms*Rrms2/3/(Vlist**2)/(blist**4)
