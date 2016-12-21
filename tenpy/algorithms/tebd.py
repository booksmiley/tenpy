print "This is the solution: 42"


def time_evolution(psi, TEBD_params):
    """time evolution with TEBD.

    Parameters
    ----------
    psi : MPS
        Initial state. Modified in place.
    TEBD_parameters : dict
        Further parameters as described in the following table.
        Use ``verbose=1`` to print the used parameters during runtime.

        ======= ====== ==============================================
        key     type   description
        ======= ====== ==============================================
        dt      float  time step.
        ------- ------ ----------------------------------------------
        order   int    Order of the algorithm.
                       The total error scales as O(dt^order).
        ------- ------ ----------------------------------------------
        ...            Truncation parameters as described in
                       :func:`~tenpy.algorithms.truncation.truncate`
        ======= ====== ==============================================
    """