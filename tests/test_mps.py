"""A collection of tests for :module:`tenpy.networks.mps`."""
# Copyright 2018-2020 TeNPy Developers, GNU GPLv3

import numpy as np
import numpy.testing as npt
import warnings
from tenpy.models.xxz_chain import XXZChain
from tenpy.models.lattice import Square

from tenpy.networks import mps, site
from tenpy.networks.terms import TermList
from random_test import rand_permutation, random_MPS
import tenpy.linalg.np_conserved as npc

import pytest

spin_half = site.SpinHalfSite(conserve='Sz')


def test_mps():
    site_triv = site.SpinHalfSite(conserve=None)
    psi = mps.MPS.from_product_state([site_triv] * 4, [0, 1, 0, 1], bc='finite')
    psi.test_sanity()
    for L in [4, 2, 1]:
        print(L)
        state = (spin_half.state_indices(['up', 'down']) * L)[:L]
        psi = mps.MPS.from_product_state([spin_half] * L, state, bc='finite')
        psi.test_sanity()
        print(repr(psi))
        print(str(psi))
        psi2 = psi.copy()
        ov = psi.overlap(psi2)
        assert (abs(ov - 1.) < 1.e-15)
        if L > 1:
            npt.assert_equal(psi.entanglement_entropy(), 0.)  # product state has no entanglement.
        E = psi.expectation_value('Sz')
        npt.assert_array_almost_equal_nulp(E, ([0.5, -0.5] * L)[:L], 100)
        C = psi.correlation_function('Sz', 'Sz')
        npt.assert_array_almost_equal_nulp(C, np.outer(E, E), 100)
        norm_err = psi.norm_test()
        assert (np.linalg.norm(norm_err) < 1.e-13)
    # example of doc in `from_product_state`
    L = 8
    theta, phi = np.pi / 3, np.pi / 6
    p_state = ["up", "down"] * (L // 2)  # repeats entries L/2 times
    bloch_sphere_state = np.array([np.cos(theta / 2), np.exp(1.j * phi) * np.sin(theta / 2)])
    p_state[L // 2] = bloch_sphere_state  # replace one spin in center
    psi = mps.MPS.from_product_state([site_triv] * L, p_state, bc='finite', dtype=np.complex)
    eval_z = psi.expectation_value("Sigmaz")
    eval_x = psi.expectation_value("Sigmax")
    assert (eval_z[L // 2] - np.cos(theta)) < 1.e-12
    assert (eval_x[L // 2] - np.sin(theta) * np.cos(phi)) < 1.e-12


def test_mps_add():
    s = site.SpinHalfSite(conserve='Sz')
    u, d = 'up', 'down'
    psi1 = mps.MPS.from_product_state([s] * 4, [u, u, d, u], bc='finite')
    psi2 = mps.MPS.from_product_state([s] * 4, [u, d, u, u], bc='finite')
    npt.assert_equal(psi1.get_total_charge(True), [2])
    psi_sum = psi1.add(psi2, 0.5**0.5, -0.5**0.5)
    npt.assert_almost_equal(psi_sum.norm, 1.)
    npt.assert_almost_equal(psi_sum.overlap(psi1), 0.5**0.5)
    npt.assert_almost_equal(psi_sum.overlap(psi2), -0.5**0.5)
    # check overlap with singlet state
    psi = mps.MPS.from_singlets(s, 4, [(1, 2)], lonely=[0, 3], up=u, down=d, bc='finite')
    npt.assert_almost_equal(psi_sum.overlap(psi), 1.)

    psi2_prime = mps.MPS.from_product_state([s] * 4, [u, u, u, u], bc='finite')
    npt.assert_equal(psi2_prime.get_total_charge(True), [4])
    psi2_prime.apply_local_op(1, 'Sm', False, False)
    # now psi2_prime is psi2 up to gauging of charges.
    npt.assert_equal(psi2_prime.get_total_charge(True), [2])
    # can MPS.add handle this?
    psi_sum_prime = psi1.add(psi2_prime, 0.5**0.5, -0.5**0.5)
    npt.assert_almost_equal(psi_sum_prime.overlap(psi), 1.)


def test_MPSEnvironment():
    xxz_pars = dict(L=4, Jxx=1., Jz=1.1, hz=0.1, bc_MPS='finite')
    L = xxz_pars['L']
    M = XXZChain(xxz_pars)
    state = ([0, 1] * L)[:L]  # Neel state
    psi = mps.MPS.from_product_state(M.lat.mps_sites(), state, bc='finite')
    env = mps.MPSEnvironment(psi, psi)
    env.get_LP(3, True)
    env.get_RP(0, True)
    env.test_sanity()
    for i in range(4):
        ov = env.full_contraction(i)  # should be one
        print("total contraction on site", i, ": ov = 1. - ", ov - 1.)
        assert (abs(abs(ov) - 1.) < 1.e-14)
    env.expectation_value('Sz')


def test_singlet_mps():
    u, d = 'up', 'down'
    pairs = [(0, 3), (1, 6), (2, 5)]
    bond_singlets = np.array([1, 2, 3, 2, 2, 1, 0])
    lonely = [4, 7]
    L = 2 * len(pairs) + len(lonely)
    print("singlet pairs: ", pairs)
    print("lonely sites: ", lonely)
    psi = mps.MPS.from_singlets(spin_half, L, pairs, lonely=lonely, lonely_state=u, bc='finite')
    psi.test_sanity()
    print('chi = ', psi.chi)
    assert (np.all(2**bond_singlets == np.array(psi.chi)))
    ent = psi.entanglement_entropy() / np.log(2)
    npt.assert_array_almost_equal_nulp(ent, bond_singlets, 5)
    psi.entanglement_spectrum(True)  # (just check that the function runs)
    npt.assert_almost_equal(psi.norm, 1.)
    npt.assert_almost_equal(psi.overlap(psi), 1.)
    id_vals = psi.expectation_value("Id")
    npt.assert_almost_equal(id_vals, [1.] * L)
    Sz_vals = psi.expectation_value("Sigmaz")
    expected_Sz_vals = [(0. if i not in lonely else 1.) for i in range(L)]
    print("Sz_vals = ", Sz_vals)
    print("expected_Sz_vals = ", expected_Sz_vals)
    npt.assert_almost_equal(Sz_vals, expected_Sz_vals)
    ent_segm = psi.entanglement_entropy_segment(list(range(4))) / np.log(2)
    print(ent_segm)
    npt.assert_array_almost_equal_nulp(ent_segm, [2, 3, 1, 3, 2], 5)
    coord, mutinf = psi.mutinf_two_site()
    coord = [(i, j) for i, j in coord]
    mutinf[np.abs(mutinf) < 1.e-14] = 0.
    mutinf /= np.log(2)
    print(mutinf)
    for (i, j) in pairs:
        k = coord.index((i, j))
        mutinf[k] -= 2.  # S(i)+S(j)-S(ij) = (1+1-0)*log(2)
    npt.assert_array_almost_equal(mutinf, 0., decimal=14)
    product_state = [None] * L
    for i, j in pairs:
        product_state[i] = u
        product_state[j] = d
    for k in lonely:
        product_state[k] = u
    psi2 = mps.MPS.from_product_state([spin_half] * L, product_state, bc='finite')
    npt.assert_almost_equal(psi.overlap(psi2), 0.5**(0.5 * len(pairs)))


def test_charge_fluctuations():
    L = 6
    pairs = [(0, 3), (2, 4)]
    lonely = [1, 5]
    psi = mps.MPS.from_singlets(spin_half,
                                L,
                                pairs,
                                lonely=lonely,
                                lonely_state='up',
                                bc='segment')
    # mps not yet gauged to zero qtotal!
    average_charge = np.array([psi.average_charge(b) for b in range(psi.L + 1)]).T
    charge_variance = np.array([psi.charge_variance(b) for b in range(psi.L + 1)]).T
    print(average_charge)
    print(charge_variance)
    npt.assert_array_almost_equal(average_charge, [[0., 0., 0., 0., 0., 0., 0.]], decimal=14)
    npt.assert_array_almost_equal(charge_variance, [[0., 1., 1., 2., 1., 0., 0.]], decimal=14)

    # now gauge to zero qtotal
    psi.gauge_total_charge()
    average_charge = np.array([psi.average_charge(b) for b in range(psi.L + 1)]).T
    charge_variance = np.array([psi.charge_variance(b) for b in range(psi.L + 1)]).T
    print(average_charge)
    print(charge_variance)
    npt.assert_array_almost_equal(average_charge, [[0., 0., 1., 1., 1., 1., 2.]], decimal=14)
    npt.assert_array_almost_equal(charge_variance, [[0., 1., 1., 2., 1., 0., 0.]], decimal=14)


def test_mps_swap():
    L = 6
    pairs = [(0, 3), (1, 5), (2, 4)]
    pairs_swap = [(0, 2), (1, 5), (3, 4)]
    print("singlet pairs: ", pairs)
    psi = mps.MPS.from_singlets(spin_half, L, pairs, bc='finite')
    psi_swap = mps.MPS.from_singlets(spin_half, L, pairs_swap, bc='finite')
    psi.swap_sites(2)
    assert abs(psi.overlap(psi_swap) - 1.) < 1.e-15
    # now test permutation
    # recover original psi
    psi = mps.MPS.from_singlets(spin_half, L, pairs, bc='finite')
    perm = rand_permutation(L)
    pairs_perm = [(perm[i], perm[j]) for i, j in pairs]
    psi_perm = mps.MPS.from_singlets(spin_half, L, pairs_perm, bc='finite')
    psi.permute_sites(perm, verbose=2)
    print(psi.overlap(psi_perm), psi.norm_test())
    assert abs(abs(psi.overlap(psi_perm)) - 1.) < 1.e-10


def test_TransferMatrix(chi=4, d=2):
    psi = random_MPS(2, d, chi, bc='infinite', form=None)
    full_TM = npc.tensordot(psi._B[0], psi._B[0].conj(), axes=['p', 'p*'])
    full_TM = npc.tensordot(full_TM, psi._B[1], axes=['vR', 'vL'])
    full_TM = npc.tensordot(full_TM, psi._B[1].conj(), axes=[['vR*', 'p'], ['vL*', 'p*']])
    full_TM = full_TM.combine_legs([['vL', 'vL*'], ['vR', 'vR*']], qconj=[+1, -1])
    full_TM_dense = full_TM.to_ndarray()
    eta_full, w_full = np.linalg.eig(full_TM_dense)
    sort = np.argsort(np.abs(eta_full))[::-1]
    eta_full = eta_full[sort]
    w_full = w_full[:, sort]
    TM = mps.TransferMatrix(psi, psi, charge_sector=0, form=None)
    eta, w = TM.eigenvectors(3)
    print("transfer matrix yields eigenvalues ", eta)
    print(eta.shape, eta_full.shape)
    print(psi.dtype)
    # note: second and third eigenvalue are complex conjugates
    if bool(eta[2].imag > 0.) == bool(eta_full[2].imag > 0.):
        npt.assert_allclose(eta[:3], eta_full[:3])
    else:
        npt.assert_allclose(eta[:3], eta_full[:3].conj())
    # compare largest eigenvector
    w0_full = w_full[:, 0]
    w0 = w[0].to_ndarray()
    assert (abs(np.sum(w0_full)) > 1.e-20)  # should be the case for random stuff
    w0_full /= np.sum(w0_full)  # fixes norm & phase
    w0 /= np.sum(w0)
    npt.assert_allclose(w0, w0_full)


def test_compute_K():
    pairs = [(0, 1), (2, 3), (4, 5)]  # singlets on a 3x2 grid -> k_y = pi
    psi = mps.MPS.from_singlets(spin_half, 6, pairs, bc='infinite')
    psi.test_sanity()
    lat = Square(3, 2, spin_half, order='default', bc_MPS='infinite', bc='periodic')
    U, W, q, ov, te = psi.compute_K(lat, verbose=100)
    assert (ov == -1.)
    npt.assert_array_equal(W, [1.])


@pytest.mark.parametrize("bc", ['finite', 'infinite'])
def test_canonical_form(bc):
    psi = random_MPS(8, 2, 6, form=None, bc=bc)
    psi2 = psi.copy()
    norm = np.sqrt(psi2.overlap(psi2, ignore_form=True))
    print("norm =", norm)
    psi2.norm /= norm  # normalize psi2
    norm2 = psi.overlap(psi2, ignore_form=True)
    print("norm2 =", norm2)
    assert abs(norm2 - norm) < 1.e-14 * norm
    psi.canonical_form(renormalize=False)
    psi.test_sanity()
    assert abs(psi.norm - norm) < 1.e-14 * norm
    psi.norm = 1.  # normalized psi
    ov = psi.overlap(psi2, ignore_form=True)
    print("normalized states: overlap <psi_canonical|psi> = 1.-", 1. - ov)
    assert abs(ov - 1.) < 1.e-14
    print("norm_test")
    print(psi.norm_test())
    assert np.max(psi.norm_test()) < 1.e-14


def test_enlarge_mps_unit_cell():
    s = site.SpinHalfSite(conserve='Sz')
    psi = mps.MPS.from_product_state([s] * 3, ['up', 'down', 'up'], bc='infinite')
    psi0 = psi.copy()
    psi1 = psi.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        psi0.increase_L(9)
    psi1.enlarge_mps_unit_cell(3)
    for psi in [psi0, psi1]:
        psi.test_sanity()
        expval = psi.expectation_value('Sigmaz')
        npt.assert_equal(expval, [1., -1., 1.] * 3)
    # done


def test_roll_mps_unit_cell():
    s = site.SpinHalfSite(conserve='Sz')
    psi = mps.MPS.from_product_state([s] * 4, ['down', 'up', 'up', 'up'], bc='infinite')
    psi1 = psi.copy()
    psi1.roll_mps_unit_cell(1)
    psi1.test_sanity()
    npt.assert_equal(psi.expectation_value('Sigmaz'), [-1., 1., 1., 1.])
    npt.assert_equal(psi1.expectation_value('Sigmaz'), [1., -1., 1., 1.])
    psi_m_1 = psi.copy()
    psi_m_1.roll_mps_unit_cell(-1)
    psi_m_1.test_sanity()
    npt.assert_equal(psi_m_1.expectation_value('Sigmaz'), [1., 1., 1., -1.])
    psi3 = psi.copy()
    psi3.spatial_inversion()
    psi3.test_sanity()
    ov = psi3.overlap(psi_m_1)
    assert abs(ov - 1.) < 1.e-14


def test_group():
    s = site.SpinHalfSite(conserve='parity')
    psi1 = mps.MPS.from_singlets(s, 6, [(1, 3), (2, 5)], lonely=[0, 4], bc='finite')
    psi2 = psi1.copy()
    print("group n=2")
    psi2.group_sites(n=2)
    assert psi2.L == psi1.L // 2
    psi2.test_sanity()
    psi2.group_split({'chi_max': 2**3})
    psi2.test_sanity()
    ov = psi1.overlap(psi2)
    assert abs(1. - ov) < 1.e-14
    psi4 = psi1.copy()
    print("group n=4")
    psi4.group_sites(n=4)
    psi4.test_sanity()
    psi4.group_split({'chi_max': 2**3})
    psi4.test_sanity()
    ov = psi1.overlap(psi4)
    assert abs(1. - ov) < 1.e-14


def test_expectation_value_term():
    s = spin_half
    psi1 = mps.MPS.from_singlets(s, 6, [(1, 3), (2, 5)], lonely=[0, 4], bc='finite')
    ev = psi1.expectation_value_term([('Sz', 2), ('Sz', 3)])
    assert abs(0. - ev) < 1.e-14
    ev = psi1.expectation_value_term([('Sz', 1), ('Sz', 3)])
    assert abs(-0.25 - ev) < 1.e-14
    ev = psi1.expectation_value_term([('Sz', 3), ('Sz', 1), ('Sz', 4)])
    assert abs(-0.25 * 0.5 - ev) < 1.e-14
    fs = site.SpinHalfFermionSite()
    # check fermionic signs
    psi2 = mps.MPS.from_product_state([fs] * 4, ['empty', 'up', 'down', 'full'], bc="infinite")
    ev = psi2.expectation_value_term([('Cu', 2), ('Nu', 1), ('Cdu', 2)])
    assert 1. == ev
    ev2 = psi2.expectation_value_term([('Cu', 2), ('Cd', 1), ('Cdd', 1), ('Cdu', 2)])
    assert ev2 == ev
    ev3 = psi2.expectation_value_term([('Cd', 1), ('Cu', 2), ('Cdd', 1), ('Cdu', 2)])
    assert ev3 == -ev2
    # over the infinite MPS boundary
    ev = psi2.expectation_value_term([('Nu', 1), ('Nd', 4)])  # should be zero
    assert abs(ev) == 0.
    ev = psi2.expectation_value_term([('Nu', 1), ('Nd', 6)])
    assert abs(ev) == 1.
    # terms_sum
    pref = np.random.random([5])
    term_list = TermList([[('Nd', 0)],
                          [('Nu', 1), ('Nd', 2)],
                          [('Nd', 2), ('Nu', 5)],
                          [('Nu Nd', 3)],
                          [('Nu', 1), ('Nu', 5)]], pref)  # yapf: disable
    desired = sum(pref[1:])
    assert desired == sum(
        [psi2.expectation_value_term(term) * strength for term, strength in term_list])
    evsum, _ = psi2.expectation_value_terms_sum(term_list)
    assert abs(evsum - desired) < 1.e-14


def test_correlation_function():
    s = spin_half
    psi1 = mps.MPS.from_singlets(s, 6, [(1, 3), (2, 5)], lonely=[0, 4], bc='finite')
    corr1 = psi1.correlation_function('Sz', 'Sz')
    corr1_exact = 0.25 * np.array([[ 1.,  0.,  0.,  0.,  1.,  0.],
                                   [ 0.,  1.,  0., -1.,  0.,  0.],
                                   [ 0.,  0.,  1.,  0.,  0., -1.],
                                   [ 0., -1.,  0.,  1.,  0.,  0.],
                                   [ 1.,  0.,  0.,  0.,  1.,  0.],
                                   [ 0.,  0., -1.,  0.,  0.,  1.]])  # yapf: disable
    npt.assert_almost_equal(corr1, corr1_exact)
    corr1 = psi1.term_correlation_function_right([('Sz', 0)], [('Sz', 0)])
    npt.assert_almost_equal(corr1, corr1_exact[0, 1:])
    corr1 = psi1.term_correlation_function_right([('Sz', 0)], [('Sz', 1)])
    npt.assert_almost_equal(corr1, corr1_exact[0, 1:])
    corr1 = psi1.term_correlation_function_right([('Sz', 1)], [('Sz', 1)])
    npt.assert_almost_equal(corr1, corr1_exact[1, 2:])
    corr1 = psi1.term_correlation_function_right([('Sz', 1)], [('Sz', -1)])
    npt.assert_almost_equal(corr1, corr1_exact[1, 2:-1])

    corr1 = psi1.term_correlation_function_left([('Sz', 0)], [('Sz', 0)], range(0, 5), 5)
    npt.assert_almost_equal(corr1[::-1], corr1_exact[:-1, 5])
    corr1 = psi1.term_correlation_function_left([('Sz', 1)], [('Sz', 1)], range(0, 4), 4)
    npt.assert_almost_equal(corr1[::-1], corr1_exact[1:-1, 5])

    # check fermionic signs
    fs = site.SpinHalfFermionSite()
    psi2 = mps.MPS.from_product_state([fs] * 4, ['empty', 'up', 'down', 'full'], bc="infinite")
    corr2 = psi2.correlation_function('Cdu', 'Cu')
    corr2_exact = np.array([[ 0.,  0.,  0.,  0.],
                            [ 0.,  1.,  0.,  0.],
                            [ 0.,  0.,  0.,  0.],
                            [ 0.,  0.,  0.,  1.]])  # yapf: disable
    npt.assert_almost_equal(corr2, corr2_exact)
    psi3 = psi2.copy()
    from tenpy.algorithms.tebd import RandomUnitaryEvolution
    RandomUnitaryEvolution(psi3, {'N_steps': 4}).run()

    corr3 = psi3.correlation_function('Cdu', 'Cu')
    corr3_d = psi3.correlation_function('Cu', 'Cdu')
    npt.assert_almost_equal(np.diag(corr3) + np.diag(corr3_d), 1.)
    corr3 = corr3 - np.diag(np.diag(corr3))  # remove diagonal
    corr3_d = corr3_d - np.diag(np.diag(corr3_d))
    npt.assert_array_almost_equal(corr3, -corr3_d.T)  # check anti-commutation of operators

    corr = psi3.term_correlation_function_right([('Cdu', 0)], [('Cu', 0)], j_R=range(1, 4))
    npt.assert_almost_equal(corr, corr3[0, 1:])
    corr3_long = psi3.correlation_function('Cdu', 'Cu', [0], range(4, 11 * 4, 4)).flatten()
    corr3_long2 = psi3.term_correlation_function_right([('Cdu', 0)], [('Cu', 0)])
    npt.assert_array_almost_equal(corr3_long, corr3_long2)


def test_expectation_value_multisite():
    s = spin_half
    psi = mps.MPS.from_singlets(s, 6, [(0, 1), (2, 3), (4, 5)], lonely=[], bc='finite')
    SpSm = npc.outer(s.Sp.replace_labels(['p', 'p*'], ['p0', 'p0*']),
                     s.Sm.replace_labels(['p', 'p*'], ['p1', 'p1*']))
    psi1 = psi.copy()
    ev = psi.expectation_value(SpSm)
    npt.assert_almost_equal(ev, [-0.5, 0., -0.5, 0., -0.5])
    env1 = mps.MPSEnvironment(psi1, psi)
    ev = env1.expectation_value(SpSm)
    npt.assert_almost_equal(ev, [-0.5, 0., -0.5, 0., -0.5])

    psi1.apply_local_op(2, SpSm)  # multi-site operator
    ev = psi1.expectation_value(SpSm)  # normalized!
    npt.assert_almost_equal(ev, [-0.5, 0., 0.0, 0., -0.5])
    env1 = mps.MPSEnvironment(psi1, psi)
    ev = env1.expectation_value(SpSm) / psi1.overlap(psi)  # normalize
    npt.assert_almost_equal(ev, [-0.5, 0., -1., 0., -0.5])


@pytest.mark.parametrize('method', ['SVD', 'variational'])
def test_mps_compress(method, eps=1.e-13):
    # Test compression of a sum of a state with itself
    L = 5
    sites = [site.SpinHalfSite(conserve=None) for i in range(L)]
    plus_x = np.array([1., 1.]) / np.sqrt(2)
    minus_x = np.array([1., -1.]) / np.sqrt(2)
    psi = mps.MPS.from_product_state(sites, [plus_x for i in range(L)], bc='finite')
    psiOrth = mps.MPS.from_product_state(sites, [minus_x for i in range(L)], bc='finite')
    options = {'compression_method': method, 'trunc_params': {'chi_max': 30}}
    psiSum = psi.add(psi, .5, .5)
    psiSum.compress(options)

    assert (np.abs(psiSum.overlap(psi) - 1) < 1e-13)
    psiSum2 = psi.add(psiOrth, .5, .5)
    psiSum2.compress(options)
    psiSum2.test_sanity()
    assert (np.abs(psiSum2.overlap(psi) - .5) < 1e-13)
    assert (np.abs(psiSum2.overlap(psiOrth) - .5) < 1e-13)


if __name__ == "__main__":
    test_correlation_function()
