Status: SUCCESS

改动文件:
- backend/app/repositories/matrix_plan_repository.py
- backend/app/api/matrix_plans.py
- backend/tests/test_matrix_plan_execution_queue_api.py
- .superpowers/sdd/matrix-exec-task-2-report.md

测试命令:
```powershell
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_execution_queue_api.py::test_confirm_matrix_plan_returns_validation_error_when_status_is_invalid -q
$env:MYSQL_TEST_HOST='127.0.0.1'; $env:MYSQL_TEST_PORT='3306'; $env:MYSQL_TEST_DATABASE='xhs_publisher_test'; $env:MYSQL_TEST_USER='root'; $env:MYSQL_TEST_PASSWORD='123456'; .\.venv\Scripts\python -m pytest backend/tests/test_matrix_plan_execution_queue_api.py -q
```

测试结果:
- focused confirm validation test: PASS (1 passed)
- Task 2 MySQL suite: PASS (5 passed)

是否有疑虑:
- 无功能性疑虑。当前允许范围内的半成品实现已满足 brief，未追加范围外改动。
