import numpy as n
from xfab import tools
from xfab import sg
from xfab import detector
from xfab.structure import int_intensity
import variables
import sys
from ImageD11 import blobcorrector
import logging
logging.basicConfig(level=logging.DEBUG,format='%(levelname)s %(message)s')

A_id = variables.refarray().A_id


class find_refl:
    def __init__(self,param,hkl):
        self.param = param
        self.hkl = hkl
        self.grain = []
    
        # Simple transforms of input and set constants
        self.K = -2*n.pi/self.param['wavelength']
        self.S = n.array([[1, 0, 0],[0, 1, 0],[0, 0, 1]])
        
        # Detector tilt correction matrix
        self.R = tools.detect_tilt(self.param['tilt_x'],self.param['tilt_y'],self.param['tilt_z'])

        # Spatial distortion
        if self.param['spatial'] != None:
            self.spatial = blobcorrector.correctorclass(self.param['spatial'])

        # %No of images
        self.nframes = (self.param['omega_end']-self.param['omega_start'])/self.param['omega_step']
        
        # Generate Miller indices for reflections within a certain resolution
        logging.info('Generating reflections')


        print 'Finished generating reflections\n'
    
    def run(self):
        spot_id = 0
        # Generate orientations of the grains and loop over all grains
        for grainno in range(self.param['no_grains']):
            A = []
            U = self.param['U_grains_%s' %(self.param['grain_list'][grainno])]
            self.grain.append(variables.grain_cont(U))
            gr_pos = n.array(self.param['pos_grains_%s' %(self.param['grain_list'][grainno])])
            gr_eps = n.array(self.param['eps_grains_%s' %(self.param['grain_list'][grainno])])
            # Calculate the B-matrix based on the strain tensor for each grain
            B = tools.epsilon2B(gr_eps,self.param['unit_cell']) 
            V = tools.CellVolume(self.param['unit_cell'])
            grain_vol = n.pi/6 * self.param['size_grains_%s' %grainno]**3 

#            print 'GRAIN NO: ',self.param['grain_list'][grainno]
#            print 'GRAIN POSITION of grain ',self.param['grain_list'][grainno],': ',gr_pos
#            print 'STRAIN TENSOR COMPONENTS (e11 e12 e13 e22 e23 e33) of grain ',self.param['grain_list'][grainno],':\n',gr_eps
#            print 'U of grain ',self.param['grain_list'][grainno],':\n',U
            nrefl = 0
  
            # Calculate these values:
            # totalnr, grainno, refno, hkl, omega, 2theta, eta, dety, detz
            # For all reflections in Ahkl that fulfill omega_start < omega < omega_end.
            # All angles in Grain are in degrees
            for hkl in self.hkl:
                Gtmp = n.dot(B,hkl[0:3])
                Gtmp = n.dot(U,Gtmp)
                Gw =   n.dot(self.S,Gtmp)
                #Gw = self.S*U*self.B*hkl
                #print G
                Glen = n.sqrt(n.dot(Gw,Gw))
                tth = 2*n.arcsin(Glen/(2*abs(self.K)))
                costth = n.cos(tth)

                Omega = tools.find_omega(Gw,tth)
  
                if len(Omega) > 0:
                    for omega in Omega:
                        if  (self.param['omega_start']*n.pi/180) < omega and\
                                omega < (self.param['omega_end']*n.pi/180):
                            Om = n.array([[n.cos(omega), -n.sin(omega), 0],
                                        [n.sin(omega),  n.cos(omega), 0],
                                        [  0       ,    0       , 1]])
                            Gt = n.dot(Om,Gw)
                            eta = n.arctan2(-Gt[1],Gt[2])
                            if eta < 0.0:  # We want eta to be [0,2pi] not [-pi,pi]
                                eta = eta +2*n.pi 
  
                            # Calc crystal position at present omega
                            [tx,ty]= n.dot(Om[:2,:2],gr_pos[:2])
                            tz = gr_pos[2]
                            
                            # Calc detector coordinate for peak 
                            (dety, detz) = detector.det_coor(Gt, 
                                                             costth,
                                                             self.param['wavelength'],
                                                             self.param['distance'],
                                                             self.param['y_size'],
                                                             self.param['z_size'],
                                                             self.param['dety_center'],
                                                             self.param['detz_center'],
                                                             self.R,
                                                             tx,ty,tz)

                            if self.param['spatial'] != None :
                                # To match the coordinate system of the spline file
                                # SPLINE(i,j): i = detz; j = (dety_size-1)-dety
                                # Well at least if the spline file is for frelon2k
                                x = detz 
                                y = self.param['dety_size']-1-dety
                                
                                (xd,yd) = self.spatial.distort(x,y)
                                detyd = self.param['dety_size']-1-yd
                                detzd = x
                            else:
                                detyd = dety
                                detzd = detz
                             #If shoebox extends outside detector exclude it
 #                           if ( self.param['sbox_y'] > detyd) or \
 #                              (detyd > self.param['dety_size']-self.param['sbox_y']) or\
 #                              (self.param['sbox_z'] > detzd) or\
 #                              (detzd > self.param['detz_size']-self.param['sbox_z']):
 #                                continue
                            
 #                           frame_center = n.floor((omega*180/n.pi-self.param['omega_start'])/self.param['omega_step'])
 #                           delta_sbox_omega =  int((self.param['sbox_omega']-1)/2)
 #                           frame_limits = [frame_center - delta_sbox_omega, frame_center + delta_sbox_omega]

                            #Polarization factor (Kahn et al, J. Appl. Cryst. (1982) 15, 330-337.)
                            rho = n.pi/2.0 + eta + self.param['beampol_direct']*n.pi/180.0 
                            P = 0.5 * (1 + costth*costth +\
                                        self.param['beampol_factor']*n.cos(2*rho)*n.sin(tth)**2)

                            #Lorentz factor
                            if eta != 0:
                                L=1/(n.sin(tth)*abs(n.sin(eta)))
                            else:
                                L=n.inf;
 
                            overlaps = 0 # set the number overlaps to zero
                            #logging.debug("frame_center: %i, omega: %f" %(frame_center,omega*180/n.pi))
                            #logging.debug("frame_limits: %i, %i" %(frame_limits[0],frame_limits[1]))
                            intensity = int_intensity(hkl[3],
                                                 L,
                                                 P,
                                                 self.param['beamflux'],
                                                 self.param['wavelength'],
                                                 V,
                                                 grain_vol)
                            A.append([grainno,nrefl,spot_id,
                                      hkl[0],hkl[1],hkl[2],
                                      tth,omega,eta,
                                      dety,detz,
                                      detyd,detzd,
                                      Gw[0],Gw[1],Gw[2],
                                      L,P,hkl[3],intensity])
                            nrefl = nrefl+1
                            spot_id = spot_id+1

#           print 'Length of Grain', len(self.grain[0].refl)
            A = n.array(A)
            A = A[n.argsort(A,0)[:,A_id['omega']],:] # sort rows according to omega
            A[:,A_id['ref_id']] = n.arange(nrefl)     # Renumber the reflections  
            A[:,A_id['spot_id']] = n.arange(n.min(A[:,A_id['spot_id']]),
                                            n.max(A[:,A_id['spot_id']])+1) # Renumber the spot_id
 
            # save reflection info in grain container
            self.grain[grainno].refs = A 
            print '\rDone %3i grain(s) of %3i' %(grainno+1,self.param['no_grains']),
            sys.stdout.flush()

        print '\n'

    def overlap(self):
        
        dtth = 1*n.pi/180.  # Don't compare position of refs further apart than dtth 

        # build one big array of reflection info of all grains
        A = self.grain[0].refs
        for grainno in range(1,self.param['no_grains']):
            A = n.concatenate((A,self.grain[grainno].refs))
        logging.debug('Finished concatenating ref arrays')
        A = A[n.argsort(A,0)[:,A_id['tth']],:] # sort rows according to tth
        logging.debug('Sorted full ref array after twotheta')
        nrefl = A.shape[0]
        
        nover=n.zeros((nrefl))
        logging.debug('Ready to compare all %i reflections',nrefl)
        overlaps = dict([(i,[]) for i in range(nrefl)])
        for i in range(1,nrefl):
            if i%1000 == 0:
                logging.debug('Comparing reflection %i', i)
            j=i-1
            while j > -1 and A[i,A_id['tth']]-A[j,A_id['tth']] < dtth :
                if abs(A[i,A_id['omega']]-A[j,A_id['omega']]) \
                        < n.pi/180.0*self.param['omega_step']*self.param['sbox_omega']:
                    peak_distance = n.sqrt((A[i,A_id['detyd']]-A[j,A_id['detyd']])**2+\
                        (A[i,A_id['detzd']]-A[j,A_id['detzd']])**2)
                    if peak_distance < (self.param['sbox_y']+self.param['sbox_z'])/2.0:
                            overlaps[A[i,A_id['spot_id']]].append([A[j,A_id['grain_id']],
                                                                   A[j,A_id['ref_id']]])
                            overlaps[A[j,A_id['spot_id']]].append([A[i,A_id['grain_id']],
                                                                   A[i,A_id['ref_id']]])
                            self.grain[int(A[i,A_id['grain_id']])].refs[A[i,A_id['ref_id']],
                                                                        A_id['overlaps']] += 1
                            self.grain[int(A[j,A_id['grain_id']])].refs[A[j,A_id['ref_id']],
                                                                        A_id['overlaps']] += 1
                j = j - 1
        print 'Number of overlaps %i out of %i refl.' %(n.sum(nover),nrefl)
        co = 0
        # How to find the info for reflection with spot_id
        #refl_with_spotid = A[(A[:,A_id['spot_id']]==spot_id),:]
        
        for i in range(nrefl):
            if len(overlaps[i]) > 0:
                co +=1
                print i, overlaps[i]
        print co

    def save(self,grainno=None):
        if grainno == None:
            savegrains = range(len(self.grain))
        else:
            savegrains = grainno
        for grainno in savegrains:
            A = self.grain[grainno].refs
            setno = 0
            filename = '%s/%s_gr%0.4d_set%0.4d.ref' \
                %(self.param['direc'],self.param['prefix'],grainno,setno)
            f = open(filename,'w')
            format = "%d "*6 + "%f "*14 + "%d "*1 + "\n"
            ( nrefl, ncol ) = A.shape
#            print nrefl, ncol
            out = "#"
            A_col = dict([[v,k] for k,v in A_id.items()])
            for col in A_col:
                out = out + ' %s' %A_col[col]
            out = out +"\n"

            f.write(out)
            for i in range(nrefl):
                out = format %(A[i,A_id['grain_id']],
                               A[i,A_id['ref_id']],
                               A[i,A_id['spot_id']],   
                               A[i,A_id['h']],
                               A[i,A_id['k']],
                               A[i,A_id['l']],
                               A[i,A_id['tth']]*180/n.pi,
                               A[i,A_id['omega']]*180/n.pi,
                               A[i,A_id['eta']]*180/n.pi,
                               A[i,A_id['dety']],
                               A[i,A_id['detz']],
                               A[i,A_id['detyd']],
                               A[i,A_id['detzd']],
                               A[i,A_id['gv1']],
                               A[i,A_id['gv2']],
                               A[i,A_id['gv3']],
                               A[i,A_id['L']],
                               A[i,A_id['P']],
                               A[i,A_id['F2']],
                               A[i,A_id['Int']],
                               A[i,0]
#                               A[i,A_id['overlaps']]
                           )
                f.write(out)
        
            f.close()   
            
    
    def write_gve(self):
        """
        Write gvector (gve) file, for format see
        http://fable.wiki.sourceforge.net/imaged11+-+file+formats
        
        Henning Osholm Sorense, RisoeDTU, 2008.
        python translation: Jette Oddershede, Risoe DTU, March 31 2008
        """

        filename = '%s/%s.gve' %(self.param['direc'],self.param['prefix'])
        f = open(filename,'w')
        lattice = sg.sg(sgno=self.param['sgno']).name[0]
        format = "%f "*6 + "%s "*1 +"\n"
        out = format %(self.param['unit_cell'][0],self.param['unit_cell'][1],
                       self.param['unit_cell'][2],self.param['unit_cell'][3],
                       self.param['unit_cell'][4],self.param['unit_cell'][5], lattice)
        f.write(out)
        out = "# wavelength = %s\n" %(self.param['wavelength'])
        f.write(out)
        out = "# wedge = 0\n"
        f.write(out)
        out = "# ds h k l\n" 
        f.write(out)
		
        A = self.grain[0].refs
        A = A[n.argsort(A,0)[:,A_id['tth']],:] # sort rows according to tth, descending
        format = "%f "*1 + "%d "*3 +"\n"
        for i in range(A.shape[0]):
            out = format %((2*n.sin(.5*A[i,A_id['tth']])/self.param['wavelength']),
                           A[i,A_id['h']],
                           A[i,A_id['k']],
                           A[i,A_id['l']]
                            )
            f.write(out)

        out = "# xr yr zr dety detz ds eta omega\n" 
        f.write(out)
        format = "%f "*8 + "\n"
        for grainno in range(1,self.param['no_grains']):
            A = n.concatenate((A,self.grain[grainno].refs))
			
        nrefl = A.shape[0]
        for i in range(nrefl):
            out = format %(A[i,A_id['gv1']]/(2*n.pi),
                           A[i,A_id['gv2']]/(2*n.pi),
                           A[i,A_id['gv3']]/(2*n.pi),
                           A[i,A_id['dety']],
                           A[i,A_id['detz']],
                           (2*n.sin(.5*A[i,A_id['tth']])/self.param['wavelength']),
                           A[i,A_id['eta']]*180/n.pi,
                           A[i,A_id['omega']]*180/n.pi
                           )
            f.write(out)
		
        f.close()   
            
    
