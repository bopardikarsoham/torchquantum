import argparse
import pdb
import torch
import torchquantum as tq
import numpy as np

from qiskit import Aer, execute
from torchpack.utils.logging import logger
from torchquantum.utils import (switch_little_big_endian_matrix,
                                switch_little_big_endian_state)
from test.static_mode_test import QLayer as AllRandomLayer
from torchquantum.plugins import tq2qiskit
from torchquantum.macro import F_DTYPE


def find_global_phase(mat1, mat2, threshold):
    for i in range(mat1.shape[0]):
        for j in range(mat1.shape[1]):
            # find a numerical stable global phase
            if np.abs(mat1[i][j]) > threshold and \
                    np.abs(mat1[i][j]) > threshold:
                return mat2[i][j] / mat1[i][j]
    return None


def unitary_tq_vs_qiskit_test():
    for n_wires in range(2, 10):
        q_dev = tq.QuantumDevice(n_wires=n_wires)
        x = torch.randn((1, 100000), dtype=F_DTYPE)
        q_layer = AllRandomLayer(n_wires=n_wires,
                                 wires=list(range(n_wires)),
                                 n_ops_rd=500,
                                 n_ops_cin=500,
                                 n_funcs=500,
                                 qiskit_compatible=True)

        unitary_tq = q_layer.get_unitary(q_dev, x)
        unitary_tq = switch_little_big_endian_matrix(unitary_tq.data.numpy())

        # qiskit
        circ = tq2qiskit(q_layer, x)
        simulator = Aer.get_backend('unitary_simulator')
        result = execute(circ, simulator).result()
        unitary_qiskit = result.get_unitary(circ)

        stable_threshold = 1e-5
        try:
            # WARNING: need to remove the global phase! The qiskit simulated
            # results sometimes has global phase shift.
            global_phase = find_global_phase(unitary_tq, unitary_qiskit,
                                             stable_threshold)

            if global_phase is None:
                logger.exception(f"Cannot find a stable enough factor to "
                                 f"reduce the global phase, increase the "
                                 f"stable_threshold and try again")
                raise RuntimeError

            assert np.allclose(unitary_tq * global_phase, unitary_qiskit,
                               atol=1e-6)
            logger.info(f"PASS tq vs qiskit [n_wires]={n_wires}")

        except AssertionError:
            logger.exception(f"FAIL tq vs qiskit [n_wires]={n_wires}")
            raise AssertionError

        except RuntimeError:
            raise RuntimeError

    logger.info(f"PASS tq vs qiskit unitary test")


def state_tq_vs_qiskit_test():
    bsz = 1
    for n_wires in range(2, 10):
        q_dev = tq.QuantumDevice(n_wires=n_wires)
        q_dev.reset_states(bsz=bsz)

        x = torch.randn((1, 100000), dtype=F_DTYPE)
        q_layer = AllRandomLayer(n_wires=n_wires,
                                 wires=list(range(n_wires)),
                                 n_ops_rd=500,
                                 n_ops_cin=500,
                                 n_funcs=500,
                                 qiskit_compatible=True)

        q_layer(q_dev, x)
        state_tq = q_dev.states.reshape(bsz, -1)
        state_tq = switch_little_big_endian_state(state_tq.data.numpy())

        # qiskit
        circ = tq2qiskit(q_layer, x)
        # Select the StatevectorSimulator from the Aer provider
        simulator = Aer.get_backend('statevector_simulator')

        # Execute and get counts
        result = execute(circ, simulator).result()
        state_qiskit = result.get_statevector(circ)

        stable_threshold = 1e-5
        try:
            # WARNING: need to remove the global phase! The qiskit simulated
            # results sometimes has global phase shift.
            global_phase = find_global_phase(state_tq,
                                             np.expand_dims(state_qiskit, 0),
                                             stable_threshold)

            if global_phase is None:
                logger.exception(f"Cannot find a stable enough factor to "
                                 f"reduce the global phase, increase the "
                                 f"stable_threshold and try again")
                raise RuntimeError

            assert np.allclose(state_tq * global_phase, state_qiskit,
                               atol=1e-6)
            logger.info(f"PASS tq vs qiskit [n_wires]={n_wires}")

        except AssertionError:
            logger.exception(f"FAIL tq vs qiskit [n_wires]={n_wires}")
            raise AssertionError

        except RuntimeError:
            raise RuntimeError

    logger.info(f"PASS tq vs qiskit statevector test")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdb', action='store_true', help='pdb')
    args = parser.parse_args()

    # seed = 45
    # torch.manual_seed(seed)
    # np.random.seed(seed)

    if args.pdb:
        pdb.set_trace()

    unitary_tq_vs_qiskit_test()
    state_tq_vs_qiskit_test()
