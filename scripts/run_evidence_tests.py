from tests import test_evidence_harvest_and_teardown as t

if __name__ == '__main__':
    t.test_build_evidence_from_orchestration_minimal()
    t.test_execute_teardown_simulated()
    print('OK')
