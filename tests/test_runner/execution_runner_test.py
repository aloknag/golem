import json
import os
from types import SimpleNamespace

import pytest

from golem.test_runner import execution_runner as exc_runner
from golem.core import (test_case, test_data, environment_manager,
                        utils, settings_manager, test_execution,
                        file_manager)
from golem.gui import report_parser


class TestDefineBrowsers:

    remote_browsers = {
        'chrome_60_mac': {
            'browserName': 'chrome',
            'version': '60.0',
            'platform': 'macOS 10.12'
        }
    }

    default_browsers = ['chrome', 'chrome-headless']

    def test_define_browsers(self):
        """Verify that _define_browsers returns the correct values"""
        browsers = ['chrome', 'chrome_60_mac']
        expected = [
            {
                'name': 'chrome',
                'full_name': None,
                'remote': False,
                'capabilities': {}
            },
            {
                'name': 'chrome',
                'full_name': 'chrome_60_mac',
                'remote': True,
                'capabilities': {
                    'browserName': 'chrome',
                    'version': '60.0',
                    'platform': 'macOS 10.12'
                }
            }
        ]
        drivers_defined = exc_runner.define_browsers(browsers, self.remote_browsers,
                                                     self.default_browsers)
        assert drivers_defined == expected

    def test_define_browsers_drivers_empty(self):
        """Verify that _define_browsers returns correct value
        when selected drivers is empty
        """
        drivers = []
        expected = []
        drivers_defined = exc_runner.define_browsers(drivers, self.remote_browsers,
                                                     self.default_browsers)
        assert drivers_defined == expected

    def test_define_browsers_driver_is_not_defined(self):
        """Verify that _define_browsers raises the correct exception
        when a driver name that is not defined is passed
        """
        drivers = ['not_defined']
        expected_msg = ['Error: the browser {} is not defined\n'.format('not_defined'),
                        'available options are:\n',
                        '\n'.join(self.default_browsers),
                        '\n'.join(list(self.remote_browsers.keys()))]
        expected_msg = ''.join(expected_msg)
        with pytest.raises(Exception) as excinfo:      
            _ = exc_runner.define_browsers(drivers, self.remote_browsers, self.default_browsers)
        assert str(excinfo.value) == expected_msg

    def test_define_browsers_browser_order_of_preference(self):
        """Verify that _define_browsers selects the drivers in the correct
        order of precedence, first remote drivers then predefined drivers"""
        remote_drivers = {
            'chromex': {
                'browserName': 'chrome',
                'version': '60.0',
                'platform': 'macOS 10.12'
            }
        }
        default_drivers = ['chromex']
        drivers = ['chromex']
        drivers_defined = exc_runner.define_browsers(drivers, remote_drivers, default_drivers)
        assert len(drivers_defined) == 1
        assert drivers_defined[0]['remote'] == True
        assert drivers_defined[0]['capabilities']['version'] == '60.0'


class TestSelectEnvironments:

    @pytest.mark.slow
    def test__select_environments(self, project_session):
        """Verify that _select_environments uses the correct order
        of precedence"""
        cli_envs = ['cli_env_1', 'cli_env_2']
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.project = project_session.name
        execution_runner.cli_args.envs = cli_envs
        execution_runner.suite.envs = ['suite_env_1', 'suite_env_2']
        result_envs = execution_runner._select_environments()
        assert result_envs == cli_envs

    @pytest.mark.slow
    def test__select_environments_cli_envs_empty(self, project_function):
        """Verify that _select_environments uses the correct order
        of precedence when cli environments is empty"""
        cli_envs = []
        suite_envs = ['suite_env_1', 'suite_env_2']
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.project = project_function.name
        execution_runner.cli_args.envs = cli_envs
        execution_runner.suite.envs = suite_envs
        path = os.path.join(project_function.path, 'environments.json')
        with open(path, 'w+') as f:
            f.write('{"env1": {}, "env2": {}}')
        result_envs = execution_runner._select_environments()
        assert result_envs == suite_envs

    @pytest.mark.slow
    def test__select_environments_cli_envs_empty_suite_envs_empty(self, project_function):
        """Verify that _select_environments uses the correct order
        of precedence when cli environments and suite environments are empty"""
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.project = project_function.name
        execution_runner.cli_args.envs = []
        execution_runner.suite.envs = []
        path = os.path.join(project_function.path, 'environments.json')
        with open(path, 'w+') as f:
            f.write('{"env3": {}, "env4": {}}')
        result_envs = execution_runner._select_environments()
        assert result_envs == ['env3']

    @pytest.mark.slow
    def test__select_environments_all_envs_empty(self, project_function):
        """Verify that _select_environments uses the correct order
        of precedence when cli environments, suite environments and 
        project environments are empty"""
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.project = project_function.name
        execution_runner.cli_args.envs = []
        execution_runner.cli_args.envs = []
        result_envs = execution_runner._select_environments()
        assert result_envs == ['']


class TestDefineExecutionList:

    @pytest.mark.slow
    def test_define_execution_list(self, project_function_clean):
        """Verify that the execution list is generated properly when there's only
        one test without datasets, one driver and zero environments
        """
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = ['test_001']
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome']
        execution_runner.execution.envs = ['']
        execution_runner.project = project_function_clean.name
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name='test_001', data_set={}, secrets={}, browser='chrome', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_multiple_data_sets(self, project_function_clean):
        """Verify that the execution list is generated properly when a test
        has multiple data sets
        """
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        os.chdir(testdir)
        test_name = 'test_002'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name)
        tdata = [
            {
                'col1': 'a',
                'col2': 'b'
            },
            {
                'col1': 'c',
                'col2': 'd',
            }

        ]
        test_data.save_external_test_data_file(testdir, project, test_name, tdata)
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = [test_name]
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome']
        execution_runner.execution.envs = ['']
        execution_runner.project = project_function_clean.name
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name=test_name, data_set={'col1': 'a', 'col2': 'b'}, secrets={},
                            browser='chrome', reportdir=None),
            SimpleNamespace(name=test_name, data_set={'col1': 'c', 'col2': 'd'}, secrets={},
                            browser='chrome', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_multiple_tests(self, project_function_clean):
        """Verify that the execution list is generated properly when there
        are multiple tests in the list
        """
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        os.chdir(testdir)
        # create test one
        test_name_one = 'test_one_001'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_one)
        tdata = [
            {
                'col1': 'a',
                'col2': 'b'
            },
            {
                'col1': 'c',
                'col2': 'd',
            }
        ]
        test_data.save_external_test_data_file(testdir, project, test_name_one, tdata)
        # create test two
        test_name_two = 'test_two_001'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_two)
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = [test_name_one, test_name_two]
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome']
        execution_runner.execution.envs = ['']
        execution_runner.project = project
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name='test_one_001', data_set={'col1': 'a', 'col2': 'b'}, secrets={},
                            browser='chrome', reportdir=None),
            SimpleNamespace(name='test_one_001', data_set={'col1': 'c', 'col2': 'd'}, secrets={},
                            browser='chrome', reportdir=None),
            SimpleNamespace(name='test_two_001', data_set={}, secrets={},
                            browser='chrome', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_multiple_envs(self, project_function_clean):
        """Verify that the execution list is generated properly when the execution
        has multiple envs
        """
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        os.chdir(testdir)
        # create test one
        test_name_one = 'test_one_003'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_one)
        # create two environments in environments.json
        env_data = {
            "stage": {"url": "xxx"},
            "preview": {"url": "yyy"}
        }
        env_data_json = json.dumps(env_data)
        environment_manager.save_environments(testdir, project, env_data_json)
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = [test_name_one]
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome']
        execution_runner.execution.envs = ['stage', 'preview']
        execution_runner.project = project
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name='test_one_003', data_set={'env': {'url': 'xxx', 'name': 'stage'}}, secrets={},
                            browser='chrome', reportdir=None),
            SimpleNamespace(name='test_one_003', data_set={'env': {'url': 'yyy', 'name': 'preview'}}, secrets={},
                            browser='chrome', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_multiple_drivers(self, project_function_clean):
        """Verify that the execution list is generated properly when there
        are multiple drivers in the list
        """
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        os.chdir(testdir)
        # create test one
        test_name_one = 'test_one_004'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_one)
        # create test two
        test_name_two = 'test_two_004'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_two)
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = [test_name_one, test_name_two]
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome', 'firefox']
        execution_runner.execution.envs = ['']
        execution_runner.project = project
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name='test_one_004', data_set={}, secrets={}, browser='chrome', reportdir=None),
            SimpleNamespace(name='test_one_004', data_set={}, secrets={}, browser='firefox', reportdir=None),
            SimpleNamespace(name='test_two_004', data_set={}, secrets={}, browser='chrome', reportdir=None),
            SimpleNamespace(name='test_two_004', data_set={}, secrets={}, browser='firefox', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_multiple_tests_datasets_drivers_envs(
            self, project_function_clean):
        """Verify that the execution list is generated properly when there
        are multiple tests, data sets, drivers and environments
        """
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        os.chdir(testdir)
        # create test one
        test_name_one = 'test_one_005'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_one)
        # test data for test one
        tdata = [
            {
                'col1': 'a',
            },
            {
                'col1': 'b',
            }

        ]
        test_data.save_external_test_data_file(testdir, project, test_name_one, tdata)
        # create test two
        test_name_two = 'test_two_005'
        parents = []
        test_case.new_test_case(testdir, project, parents, test_name_two)
        # create two environments
        env_data = {
            "stage": {
                "url": "xxx"
            },
            "preview": {
                "url": "yyy"
            }
        }
        env_data_json = json.dumps(env_data)
        environment_manager.save_environments(testdir, project, env_data_json)
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = [test_name_one, test_name_two]
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome', 'firefox']
        execution_runner.execution.envs = ['stage', 'preview']
        execution_runner.project = project
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(browser='chrome', data_set={'col1': 'a', 'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'col1': 'a', 'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='chrome', data_set={'col1': 'a', 'env': {'url': 'yyy', 'name': 'preview'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'col1': 'a', 'env': {'url': 'yyy', 'name': 'preview'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='chrome', data_set={'col1': 'b', 'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'col1': 'b', 'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='chrome', data_set={'col1': 'b', 'env': {'url': 'yyy', 'name': 'preview'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'col1': 'b', 'env': {'url': 'yyy', 'name': 'preview'}}, secrets={}, name='test_one_005', reportdir=None),
            SimpleNamespace(browser='chrome', data_set={'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_two_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'env': {'url': 'xxx', 'name': 'stage'}}, secrets={}, name='test_two_005', reportdir=None),
            SimpleNamespace(browser='chrome', data_set={'env': {'url': 'yyy', 'name': 'preview'}}, secrets={}, name='test_two_005', reportdir=None),
            SimpleNamespace(browser='firefox', data_set={'env': {'url': 'yyy','name': 'preview'}}, secrets={}, name='test_two_005', reportdir=None)
        ]
        assert execution_list == expected_list

    @pytest.mark.slow
    def test_define_execution_list_with_secrets(self, project_function_clean):
        """Verify that the execution list is generated properly when there's only
        one test without datasets, one driver and zero environments
        """
        secrets = {"a": "secret", "b": "secret02"}
        testdir = project_function_clean.testdir
        project = project_function_clean.name
        secrets_path = os.path.join(project_function_clean.path, 'secrets.json')
        with open(secrets_path, 'w') as secrets_file:
            secrets_file.write(json.dumps(secrets, indent=True))
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = ['test_001']
        execution_runner.execution.processes = 1
        execution_runner.execution.browsers = ['chrome']
        execution_runner.execution.envs = ['']
        execution_runner.project = project_function_clean.name
        execution_list = execution_runner._define_execution_list()
        expected_list = [
            SimpleNamespace(name='test_001', data_set={}, secrets={"a": "secret", "b": "secret02"}, browser='chrome', reportdir=None)
        ]
        assert execution_list == expected_list


class TestCreateExecutionDirectory:

    @pytest.mark.slow
    def test__create_execution_directory_is_suite(self, project_class):
        """Verify that create_execution_directory works as expected when 
        a suite is passed on
        """
        project = project_class.name
        timestamp = utils.get_timestamp()
        suite_name = 'bar'
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.tests = ['test_foo']
        execution_runner.project = project
        execution_runner.is_suite = True
        execution_runner.suite_name = suite_name
        execution_runner.timestamp = timestamp
        execution_runner._create_execution_directory()
        expected_path = os.path.join(project_class.path, 'reports', suite_name, timestamp)
        assert os.path.isdir(expected_path)

    @pytest.mark.slow
    def test__create_execution_directory_is_not_suite(self, project_class):
        """Verify that create_execution_directory works as expected when 
        a not suite is passed on
        """
        project = project_class.name
        test_name = 'foo'
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner()
        execution_runner.test_name = test_name
        execution_runner.project = project
        execution_runner.is_suite = False
        execution_runner.timestamp = timestamp
        execution_runner._create_execution_directory()
        expected_path = os.path.join(project_class.path, 'reports', 'single_tests', test_name, timestamp)
        assert os.path.isdir(expected_path)


class TestRunSingleTest:

    def test_run_single_test(self, project_class, test_utils):
        testdir = project_class.testdir
        project = project_class.name
        test_name = 'foo001'
        timestamp = utils.get_timestamp()
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        test_utils.create_test(testdir, project, [], test_name)
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_test(test_name)
        test_report_dir = os.path.join(testdir, 'projects', project, 'reports',
                                       'single_tests', test_name, timestamp)
        assert os.path.isdir(test_report_dir)
        items = os.listdir(test_report_dir)
        # test set dir + report.json
        assert len(items) == 2

    def test_run_single_test_with_two_sets(self, project_class, test_utils, capsys):
        """Run a single test with two data sets.
        It should display the number of tests and test sets found."""
        testdir = project_class.testdir
        project = project_class.name
        test_name = 'foo002'
        timestamp = utils.get_timestamp()
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        content = ('data = [{"foo": 1}, {"foo": 2}]\n'
                   'def test(data):\n'
                   '    pass\n')
        test_utils.create_test(testdir, project, [], test_name, content=content)
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_test(test_name)
        out, err = capsys.readouterr()
        # number of tests is displayed
        assert 'Tests found: 1 (2 sets)' in out
        test_report_dir = os.path.join(testdir, 'projects', project, 'reports',
                                       'single_tests', test_name, timestamp)
        assert os.path.isdir(test_report_dir)
        items = os.listdir(test_report_dir)
        # two test set dirs + report.json
        assert len(items) == 3

    def test_run_single_test_filter_by_tags(self, project_class, test_utils):
        """Run a single test with filtering by tags"""
        testdir = project_class.testdir
        project = project_class.name
        test_name = 'foo003'
        timestamp = utils.get_timestamp()
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        content = ('tags = ["alfa", "bravo"]\n'
                   'def test(data):\n'
                   '    pass\n')
        test_utils.create_test(testdir, project, [], test_name, content=content)
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp,
                                                      tags=['alfa'])
        execution_runner.project = project
        execution_runner.run_test(test_name)
        test_report_dir = os.path.join(testdir, 'projects', project, 'reports',
                                       'single_tests', test_name, timestamp)
        assert os.path.isdir(test_report_dir)
        items = os.listdir(test_report_dir)
        # test set dir + report.json
        assert len(items) == 2

    def test_run_single_test_with_invalid_tags(self, project_class, test_utils, capsys):
        testdir = project_class.testdir
        project = project_class.name
        test_name = 'foo004'
        timestamp = utils.get_timestamp()
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        content = ('tags = ["alfa", "bravo"]\n'
                   'def test(data):\n'
                   '    pass\n')
        test_utils.create_test(testdir, project, [], test_name, content=content)
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp,
                                                      tags=['charlie'])
        execution_runner.project = project
        execution_runner.run_test(test_name)
        out, err = capsys.readouterr()
        assert 'No tests found with tag(s): charlie' in out
        test_report_dir = os.path.join(testdir, 'projects', project, 'reports',
                                       'single_tests', test_name, timestamp)
        assert os.path.isdir(test_report_dir)
        items = os.listdir(test_report_dir)
        # only report.json is present
        assert items == ['report.json']


class TestRunSuite:

    @pytest.fixture(scope="class")
    def _project_with_tags(self, project_class, test_utils):
        """A fixture of a project with tests that contain tags"""
        testdir = project_class.testdir
        project = project_class.name
        tests = SimpleNamespace()
        base_content = 'def test(data):\n     pass\n'
        tests.test_alfa_bravo = 'test_alfa_bravo'
        content = 'tags = ["alfa", "bravo"]'
        test_utils.create_test(testdir, project, [], tests.test_alfa_bravo,
                               content=base_content+content)
        tests.test_bravo_charlie = 'test_bravo_charlie'
        content = 'tags = ["bravo", "charlie"]'
        test_utils.create_test(testdir, project, [], tests.test_bravo_charlie,
                               content=base_content+content)
        tests.test_empty_tags = 'test_empty_tags'
        content = 'tags = []'
        test_utils.create_test(testdir, project, [], tests.test_empty_tags,
                               content=base_content+content)
        tests.test_no_tags = 'test_no_tags'
        content = 'def test(data):\n     pass'
        test_utils.create_test(testdir, project, [], tests.test_no_tags,
                               content=base_content+content)
        project_class.tests = list(tests.__dict__)
        project_class.t = tests
        return project_class

    def test_run_suite(self, _project_with_tags, test_utils, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        suite_name = test_utils.random_numeric_string(10, 'suite')
        tests = [_project_with_tags.t.test_alfa_bravo,
                 _project_with_tags.t.test_bravo_charlie]
        test_utils.create_suite(testdir, project, suite_name, tests=tests)
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_suite(suite_name)
        out, err = capsys.readouterr()
        assert 'Tests found: 2' in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=suite_name, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 2

    def test_run_suite_without_tests(self, _project_with_tags, test_utils, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        suite_name = test_utils.random_numeric_string(10, 'suite')
        test_utils.create_suite(testdir, project, suite_name, tests=[])
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_suite(suite_name)
        out, err = capsys.readouterr()
        assert 'No tests found for suite {}'.format(suite_name) in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=suite_name, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 0

    def test_run_suite_filter_by_tags(self, _project_with_tags, test_utils, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        suite_name = test_utils.random_numeric_string(10, 'suite')
        tests = [_project_with_tags.t.test_alfa_bravo,
                 _project_with_tags.t.test_bravo_charlie]
        test_utils.create_suite(testdir, project, suite_name, tests=tests)
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'],
                                                      timestamp=timestamp,
                                                      tags=['alfa', 'bravo'])
        execution_runner.project = project
        execution_runner.run_suite(suite_name)
        out, err = capsys.readouterr()
        assert 'Tests found: 1' in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=suite_name, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 1

    def test_run_suite_filter_by_invalid_tags(self, _project_with_tags, test_utils, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        suite_name = test_utils.random_numeric_string(10, 'suite')
        tests = [_project_with_tags.t.test_alfa_bravo,
                 _project_with_tags.t.test_bravo_charlie]
        test_utils.create_suite(testdir, project, suite_name, tests=tests)
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'],
                                                      timestamp=timestamp,
                                                      tags=['sierra', 'tango'])
        execution_runner.project = project
        execution_runner.run_suite(suite_name)
        out, err = capsys.readouterr()
        assert 'No tests found with tag(s): sierra, tango' in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=suite_name, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 0

    def test_run_suite_filter_by_invalid_tag_expression(self, _project_with_tags,
                                                        test_utils, capsys):
        """When a invalid tag expression is used a message is displayed
        to the console, no tests are run, the report is generated,
        and the execution exists with status code 1
        """
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        suite_name = test_utils.random_numeric_string(10, 'suite')
        tests = [_project_with_tags.t.test_alfa_bravo,
                 _project_with_tags.t.test_bravo_charlie]
        test_utils.create_suite(testdir, project, suite_name, tests=tests)
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'],
                                                      timestamp=timestamp,
                                                      tags=['sierra = tango'])
        execution_runner.project = project
        with pytest.raises(SystemExit):
            execution_runner.run_suite(suite_name)
        out, err = capsys.readouterr()
        expected = ("InvalidTagExpression: unknown expression <class '_ast.Assign'>, the "
                    "only valid operators for tag expressions are: 'and', 'or' & 'not'")
        assert expected in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=suite_name, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 0


class TestRunDirectory:

    @pytest.fixture(scope="class")
    def _project_with_tags(self, project_class, test_utils):
        """A fixture of a project with tests that contain tags"""
        testdir = project_class.testdir
        project = project_class.name
        tests = SimpleNamespace()
        base_content = 'def test(data):\n     pass\n'
        tests.test_alfa_bravo = 'test_alfa_bravo'
        content = 'tags = ["alfa", "bravo"]'
        test_utils.create_test(testdir, project, ['foo'], tests.test_alfa_bravo,
                               content=base_content + content)
        tests.test_bravo_charlie = 'test_bravo_charlie'
        content = 'tags = ["bravo", "charlie"]'
        test_utils.create_test(testdir, project, ['foo'], tests.test_bravo_charlie,
                               content=base_content + content)
        tests.test_empty_tags = 'test_empty_tags'
        content = 'tags = []'
        test_utils.create_test(testdir, project, [], tests.test_empty_tags,
                               content=base_content + content)
        tests.test_no_tags = 'test_no_tags'
        content = 'def test(data):\n     pass'
        test_utils.create_test(testdir, project, [], tests.test_no_tags,
                               content=base_content + content)
        path_list = [testdir, 'projects', project, 'tests', 'empty']
        file_manager.create_directory(path_list=path_list, add_init=True)
        project_class.tests = list(tests.__dict__)
        project_class.t = tests
        return project_class

    def test_run_directory(self, _project_with_tags, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        timestamp = utils.get_timestamp()
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_directory('foo')
        out, err = capsys.readouterr()
        assert 'Tests found: 2' in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite='foo', execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 2

    def test_run_directory_without_tests(self, _project_with_tags, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        timestamp = utils.get_timestamp()
        dirname = 'empty'
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'], timestamp=timestamp)
        execution_runner.project = project
        execution_runner.run_directory(dirname)
        out, err = capsys.readouterr()
        expected = 'No tests were found in {}'.format(os.path.join('tests', dirname))
        assert expected in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=dirname, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 0

    def test_run_directory_filter_by_tags(self, _project_with_tags, test_utils, capsys):
        testdir = _project_with_tags.testdir
        project = _project_with_tags.name
        test_execution.settings = settings_manager.get_project_settings(testdir, project)
        timestamp = utils.get_timestamp()
        dirname = 'foo'
        execution_runner = exc_runner.ExecutionRunner(browsers=['chrome'],
                                                      timestamp=timestamp,
                                                      tags=['alfa', 'bravo'])
        execution_runner.project = project
        execution_runner.run_directory(dirname)
        out, err = capsys.readouterr()
        assert 'Tests found: 1' in out
        data = report_parser.get_execution_data(workspace=testdir, project=project,
                                                suite=dirname, execution=timestamp)
        assert data['has_finished'] is True
        assert data['total_tests'] == 1
