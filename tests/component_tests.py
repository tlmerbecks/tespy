# -*- coding: utf-8
# -*- coding: utf-8

from nose.tools import ok_, eq_

from tespy import nwk, cmp, con, hlp
from CoolProp.CoolProp import PropsSI as CP
import numpy as np
import shutil


class component_tests:

    def setup(self):
        self.nw = nwk.network(['INCOMP::DowQ', 'H2O', 'NH3', 'N2', 'O2', 'Ar', 'CO2', 'CH4'],
                              T_unit='C', p_unit='bar', v_unit='m3 / s')
        self.source = cmp.source('source')
        self.sink = cmp.sink('sink')

    def setup_network_11(self, instance):
        """
        Set up network for components with one inlet and one outlet.
        """
        c1 = con.connection(self.source, 'out1', instance, 'in1')
        c2 = con.connection(instance, 'out1', self.sink, 'in1')
        self.nw.add_conns(c1, c2)
        return c1, c2

    def setup_network_21(self, instance):
        """
        Set up network for components with two inlets and one outlet.
        """
        c1 = con.connection(self.source, 'out1', instance, 'in1')
        c2 = con.connection(cmp.source('fuel'), 'out1', instance, 'in2')
        c3 = con.connection(instance, 'out1', self.sink, 'in1')
        self.nw.add_conns(c1, c2, c3)
        return c1, c2, c3

    def test_turbomachine(self):
        """
        Test component properties of turbomachines.
        """
        instance = cmp.turbomachine('turbomachine')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0.7556, 'O2': 0.2315, 'Ar': 0.0129, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, m=10, p=1, h=1e5)
        c2.set_attr(p=1, h=2e5)
        self.nw.solve('design')
        power = c1.m.val_SI * (c2.h.val_SI - c1.h.val_SI)
        pr = c2.p.val_SI / c1.p.val_SI
        # pressure ratio and power are the basic functions for turbomachines, these are inherited by all children, thus only tested here
        eq_(power, instance.P.val, 'Value of power must be ' + str(power) + ', is ' + str(instance.P.val) + '.')
        eq_(pr, instance.pr.val, 'Value of power must be ' + str(pr) + ', is ' + str(instance.pr.val) + '.')
        c2.set_attr(p=np.nan)
        instance.set_attr(pr=5)
        self.nw.solve('design')
        pr = c2.p.val_SI / c1.p.val_SI
        eq_(pr, instance.pr.val, 'Value of power must be ' + str(pr) + ', is ' + str(instance.pr.val) + '.')
        c2.set_attr(h=np.nan)
        instance.set_attr(P=1e5)
        self.nw.solve('design')
        power = c1.m.val_SI * (c2.h.val_SI - c1.h.val_SI)
        eq_(pr, instance.pr.val, 'Value of power must be ' + str(pr) + ', is ' + str(instance.pr.val) + '.')
        instance.set_attr(eta_s=0.8)
        c2.set_attr(h=np.nan)
        try:
            self.nw.solve('design')
        except hlp.TESPyComponentError:
            pass
        try:
            instance.eta_s_deriv()
        except hlp.TESPyComponentError:
            pass

    def test_pump(self):
        """
        Test component properties of pumps.
        """
        instance = cmp.pump('pump')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 1, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, v=1, p=5,T=50)
        c2.set_attr(p=7)
        instance.set_attr(eta_s=1)
        self.nw.solve('design')
        # calculate isentropic efficiency the old fashioned way
        eta_s = (instance.h_os('') - c1.h.val_SI) / (c2.h.val_SI - c1.h.val_SI)
        eq_(eta_s, instance.eta_s.val, 'Value of isentropic efficiency must be ' + str(eta_s) + ', is ' + str(instance.eta_s.val) + '.')
        s1 = round(hlp.s_mix_ph(c1.to_flow()), 4)
        s2 = round(hlp.s_mix_ph(c2.to_flow()), 4)
        eq_(s1, s2, 'Value of entropy must be identical for inlet (' + str(s1) + ') and outlet (' + str(s2) + ') at 100 % isentropic efficiency.')
        instance.set_attr(eta_s=0.7)
        self.nw.solve('design')
        self.nw.save('tmp')
        c2.set_attr(p=np.nan)
        # flow char (pressure rise vs. volumetric flow)
        x = [0, 0.2, 0.4, 0.6, 0.8, 1, 1.2, 1.4]
        y = np.array([14, 13.5, 12.5, 11, 9, 6.5, 3.5, 0]) * 1e5
        char = hlp.dc_cc(x=x, y=y, is_set=True)
        # apply flow char and eta_s char
        instance.set_attr(flow_char=char, eta_s=np.nan, eta_s_char=hlp.dc_cc(method='GENERIC', is_set=True))
        self.nw.solve('offdesign', design_path='tmp')
        eq_(c2.p.val_SI - c1.p.val_SI, 6.5e5, 'Value of pressure rise must be ' + str(6.5e5) + ', is ' + str(c2.p.val_SI - c1.p.val_SI) + '.')
        c1.set_attr(v=0.9)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(c2.p.val_SI - c1.p.val_SI, 781250.0, 'Value of pressure rise must be ' + str(781250.0) + ', is ' + str(c2.p.val_SI - c1.p.val_SI) + '.')
        eq_(0.695, round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(0.695) + ', is ' + str(instance.eta_s.val) + '.')
        instance.eta_s_char.is_set = False
        # test boundaries of characteristic line
        c2.set_attr(T=con.ref(c1, 0, 20))
        c1.set_attr(v=-0.1)
        self.nw.solve('design')
        eq_(c2.p.val_SI - c1.p.val_SI, 14e5, 'Value of power must be ' + str(14e5) + ', is ' + str(c2.p.val_SI - c1.p.val_SI) + '.')
        c1.set_attr(v=1.5)
        self.nw.solve('design')
        eq_(c2.p.val_SI - c1.p.val_SI, 0, 'Value of power must be ' + str(0) + ', is ' + str(c2.p.val_SI - c1.p.val_SI) + '.')
        shutil.rmtree('./tmp', ignore_errors=True)

    def test_compressor(self):
        """
        Test component properties of compressors.
        """
        instance = cmp.compressor('compressor')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 1, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, v=1, p=5, T=100)
        c2.set_attr(p=7)
        instance.set_attr(eta_s=0.8)
        self.nw.solve('design')
        self.nw.save('tmp')
        # calculate isentropic efficiency the old fashioned way
        eta_s = (instance.h_os('') - c1.h.val_SI) / (c2.h.val_SI - c1.h.val_SI)
        eq_(round(eta_s, 3), round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(eta_s) + ', is ' + str(instance.eta_s.val) + '.')
        c2.set_attr(p=np.nan)
        instance.set_attr(char_map=hlp.dc_cm(method='GENERIC', is_set=True), eta_s=np.nan)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(round(eta_s, 2), round(instance.eta_s.val, 2), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be identical to design case (' + str(eta_s) + ').')
        # going above highes available speedline, beneath lowest mass flow at that line
        c1.set_attr(v=np.nan, m=c1.m.val*0.8, T=30)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(round(eta_s * instance.char_map.z2[6, 0], 4), round(instance.eta_s.val, 4), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be at (' + str(round(eta_s * instance.char_map.z2[6, 0], 4)) + ').')
        # going below lowest available speedline, above highest mass flow at that line
        c1.set_attr(T=300)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(round(eta_s * instance.char_map.z2[0, 9], 4), round(instance.eta_s.val, 4), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be at (' + str(round(eta_s * instance.char_map.z2[0, 9], 4)) + ').')
        # back to design properties, test eta_s_char
        c2.set_attr(p=7)
        c1.set_attr(v=1, T=100, m=np.nan)
        # test param specification m
        instance.set_attr(eta_s_char=hlp.dc_cc(method='GENERIC', is_set=True, param='m'))
        instance.char_map.is_set = False
        self.nw.solve('offdesign', design_path='tmp')
        eq_(round(eta_s, 3), round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(eta_s) + ', is ' + str(instance.eta_s.val) + '.')
        c1.set_attr(v=1.5)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.82, round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(0.82) + ', is ' + str(instance.eta_s.val) + '.')
        # test param specification pr
        instance.eta_s_char.set_attr(param='pr')
        c1.set_attr(v=1)
        c2.set_attr(p=7.5)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.797, round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(0.797) + ', is ' + str(instance.eta_s.val) + '.')
        instance.eta_s_char.set_attr(param=None)
        # test for missing parameter declaration
        try:
            self.nw.solve('offdesign', design_path='tmp')
        except ValueError:
            pass
        shutil.rmtree('./tmp', ignore_errors=True)

    def test_turbine(self):
        """
        Test component properties of turbines.
        """
        instance = cmp.turbine('turbine')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0.7556, 'O2': 0.2315, 'Ar': 0.0129, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, m=15, p=10, T=120)
        c2.set_attr(p=1)
        instance.set_attr(eta_s=0.8)
        self.nw.solve('design')
        self.nw.save('tmp')
        # calculate isentropic efficiency the old fashioned way
        eta_s = (c2.h.val_SI - c1.h.val_SI) / (instance.h_os('') - c1.h.val_SI)
        eq_(round(eta_s, 3), round(instance.eta_s.val, 3), 'Value of isentropic efficiency must be ' + str(eta_s) + ', is ' + str(instance.eta_s.val) + '.')
        c1.set_attr(p=np.nan)
        instance.cone.is_set = True
        instance.eta_s_char.is_set = True
        instance.eta_s.is_set = False
        self.nw.solve('offdesign', design_path='tmp')
        eq_(round(eta_s, 2), round(instance.eta_s.val, 2), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be identical to design case (' + str(eta_s) + ').')
        # lowering mass flow, inlet pressure must sink according to cone law
        c1.set_attr(m=c1.m.val*0.8)
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.125, round(instance.pr.val, 3), 'Value of pressure ratio (' + str(instance.pr.val) + ') must be at (' + str(0.125) + ').')
        self.nw.print_results()
        # testing more parameters for eta_s_char
        c1.set_attr(m=10)
        # test param specification v
        instance.eta_s_char.param='v'
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.8, round(instance.eta_s.val, 3), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be (' + str(0.8) + ').')
        # test param specification pr
        instance.eta_s_char.param='pr'
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.792, round(instance.eta_s.val, 3), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be (' + str(0.792) + ').')
        # test param specification dh_s
        instance.eta_s_char.param='dh_s'
        self.nw.solve('offdesign', design_path='tmp')
        eq_(0.798, round(instance.eta_s.val, 3), 'Value of isentropic efficiency (' + str(instance.eta_s.val) + ') must be (' + str(0.798) + ').')
        instance.eta_s_char.param=None
        # test for missing parameter declaration
        try:
            self.nw.solve('offdesign', design_path='tmp')
        except ValueError:
            pass
        shutil.rmtree('./tmp', ignore_errors=True)

    def test_combustion_chamber(self):
        """
        Test component properties of combustion chambers.
        """
        instance = cmp.combustion_chamber('combustion chamber', fuel='CH4')
        c1, c2, c3 = self.setup_network_21(instance)
        air = {'N2': 0.7556, 'O2': 0.2315, 'Ar': 0.0129, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        fuel = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0.04, 'CH4': 0.96}
        c1.set_attr(fluid=air, p=1, T=30)
        c2.set_attr(fluid=fuel, T=30)
        c3.set_attr(T=1200)
        b = con.bus('thermal input', P=1e6)
        b.add_comps({'c': instance})
        self.nw.add_busses(b)
        self.nw.solve('design')
        self.nw.print_results()
        eq_(round(b.P.val, 1), round(instance.ti.val, 1), 'Value of thermal input must be ' + str(b.P.val) + ', is ' + str(instance.ti.val) + '.')

    def test_valve(self):
        """
        Test component properties of valves.
        """
        instance = cmp.valve('valve')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0.7556, 'O2': 0.2315, 'Ar': 0.0129, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, m=10, p=10, T=120)
        c2.set_attr(p=1)
        instance.set_attr(pr='var')
        self.nw.solve('design')
        eq_(round(c2.p.val_SI / c1.p.val_SI, 1), round(instance.pr.val, 1), 'Value of pressure ratio must be ' + str(c2.p.val_SI / c1.p.val_SI) + ', is ' + str(instance.pr.val) + '.')
        zeta = instance.zeta.val
        instance.set_attr(zeta='var', pr=np.nan)
        self.nw.solve('design')
        eq_(round(zeta, 1), round(instance.zeta.val, 1), 'Value of pressure ratio must be ' + str(zeta) + ', is ' + str(instance.zeta.val) + '.')

    def test_cogeneration_unit(self):
        """
        Test component properties of cogeneration unit.
        """
        amb = cmp.source('ambient')
        sf = cmp.source('fuel')
        fg = cmp.sink('flue gas outlet')
        cw_in1 = cmp.source('cooling water inlet1')
        cw_in2 = cmp.source('cooling water inlet2')
        cw_out1 = cmp.sink('cooling water outlet1')
        cw_out2 = cmp.sink('cooling water outlet2')
        chp = cmp.cogeneration_unit('cogeneration unit', fuel='CH4')
        amb_comb = con.connection(amb, 'out1', chp, 'in3')
        sf_comb = con.connection(sf, 'out1', chp, 'in4')
        comb_fg = con.connection(chp, 'out3', fg, 'in1')
        self.nw.add_conns(sf_comb, amb_comb, comb_fg)
        cw1_chp1 = con.connection(cw_in1, 'out1', chp, 'in1')
        cw2_chp2 = con.connection(cw_in2, 'out1', chp, 'in2')
        self.nw.add_conns(cw1_chp1, cw2_chp2)
        chp1_cw = con.connection(chp, 'out1', cw_out1, 'in1')
        chp2_cw = con.connection(chp, 'out2', cw_out2, 'in1')
        self.nw.add_conns(chp1_cw, chp2_cw)

        air = {'N2': 0.7556, 'O2': 0.2315, 'Ar': 0.0129, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        fuel = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 0, 'NH3': 0, 'CO2': 0.04, 'CH4': 0.96}
        water1 = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 1, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        water2 = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 1, 'NH3': 0, 'CO2': 0, 'CH4': 0}

        chp.set_attr(fuel='CH4', pr1=0.99, pr2=0.99, lamb=1.2, design=['pr1', 'pr2'], offdesign=['zeta1', 'zeta2'])
        amb_comb.set_attr(p=5, T=30, fluid=air)
        sf_comb.set_attr(T=30, fluid=fuel)
        cw1_chp1.set_attr(p=3, T=60, m=50, fluid=water1)
        cw2_chp2.set_attr(p=3, T=80, m=50, fluid=water2)

        TI = con.bus('thermal input')
        Q1 = con.bus('heat output 1')
        Q2 = con.bus('heat output 2')
        Q = con.bus('heat output')
        Qloss = con.bus('thermal heat loss')

        TI.add_comps({'c': chp, 'p': 'TI'})
        Q1.add_comps({'c': chp, 'p': 'Q1'})
        Q2.add_comps({'c': chp, 'p': 'Q2'})
        Q.add_comps({'c': chp, 'p': 'Q'})
        Qloss.add_comps({'c': chp, 'p': 'Qloss'})

        self.nw.add_busses(TI, Q1, Q2, Q, Qloss)
        ti = 1e6
        TI.set_attr(P=ti)

        self.nw.solve('design')
        self.nw.save('tmp')
        self.nw.solve('offdesign', init_path='tmp', design_path='tmp')
        eq_(round(TI.P.val, 1), round(chp.ti.val, 1), 'Value of thermal input must be ' + str(TI.P.val) + ', is ' + str(chp.ti.val) + '.')
        TI.set_attr(P=np.nan)
        Q1.set_attr(P=chp.Q1.val)
        self.nw.solve('offdesign', init_path='tmp', design_path='tmp')
        eq_(round(ti, 1), round(chp.ti.val, 1), 'Value of thermal input must be ' + str(ti) + ', is ' + str(chp.ti.val) + '.')
        heat1 = chp1_cw.m.val_SI * (chp1_cw.h.val_SI - cw1_chp1.h.val_SI)
        eq_(round(heat1, 1), round(chp.Q1.val, 1), 'Value of thermal input must be ' + str(heat1) + ', is ' + str(chp.Q1.val) + '.')
        Q1.set_attr(P=np.nan)
        Q2.set_attr(P=1.2 * chp.Q2.val)
        self.nw.solve('offdesign', init_path='tmp', design_path='tmp')
        # due to characteristic function Q1 is equal to Q2 for this cogeneration unit
        heat1 = chp1_cw.m.val_SI * (chp1_cw.h.val_SI - cw1_chp1.h.val_SI)
        eq_(round(heat1, 1), round(chp.Q2.val, 1), 'Value of heat output 2 must be ' + str(heat1) + ', is ' + str(chp.Q2.val) + '.')
        Q2.set_attr(P=np.nan)
        Q.set_attr(P=1.5 * chp.Q1.val)
        self.nw.solve('offdesign', init_path='tmp', design_path='tmp')
        eq_(round(Q.P.val, 1), round(2 * chp.Q2.val, 1), 'Value of total heat output (' + str(Q.P.val) + ') must be twice as much as value of heat output 2 (' + str(chp.Q2.val) + ').')
        Q.set_attr(P=np.nan)
        Qloss.set_attr(P=1e5)
        self.nw.solve('offdesign', init_path='tmp', design_path='tmp')
        eq_(round(Qloss.P.val, 1), round(chp.Qloss.val, 1), 'Value of heat loss must be ' + str(Qloss.P.val) + ', is ' + str(chp.Qloss.val) + '.')
        shutil.rmtree('./tmp', ignore_errors=True)

    def test_heat_ex_simple(self):
        """
        Test component properties of valves.
        """
        instance = cmp.heat_exchanger_simple('heat exchanger')
        c1, c2 = self.setup_network_11(instance)
        fl = {'N2': 0, 'O2': 0, 'Ar': 0, 'INCOMP::DowQ': 0, 'H2O': 1, 'NH3': 0, 'CO2': 0, 'CH4': 0}
        c1.set_attr(fluid=fl, m=1, p=10, T=100)
        instance.set_attr(hydro_group='HW', D='var', L=100, ks=100, pr=0.99, Tamb=20)
        b = con.bus('heat', P=-1e5)
        b.add_comps({'c': instance})
        self.nw.add_busses(b)
        self.nw.solve('design')
        eq_(round(c2.p.val_SI / c1.p.val_SI, 2), round(instance.pr.val, 2), 'Value of pressure ratio must be ' + str(c2.p.val_SI / c1.p.val_SI) + ', is ' + str(instance.pr.val) + '.')
        zeta = instance.zeta.val
        instance.set_attr(D=instance.D.val, zeta='var', pr=np.nan)
        instance.D.is_var = False
        self.nw.solve('design')
        eq_(round(zeta, 1), round(instance.zeta.val, 1), 'Value of zeta must be ' + str(zeta) + ', is ' + str(instance.zeta.val) + '.')
        instance.set_attr(kA='var', zeta=np.nan)
        b.set_attr(P=-5e4)
        self.nw.solve('design')
        # due to heat output being half of reference (for Tamb) kA should be somewhere near to that (actual value is 677)
        eq_(677, round(instance.kA.val, 0), 'Value of heat transfer coefficient must be ' + str(677) + ', is ' + str(instance.kA.val) + '.')
