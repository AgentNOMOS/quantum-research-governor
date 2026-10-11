from experiments import run_r0


def test_r0_matrix_matches_expected_and_no_false_accepts():
    assert run_r0.main() == 0
