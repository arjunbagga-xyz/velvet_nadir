$env:PYTHONPATH="D:\Open Projects\seamless_computing\sw\velvet"
pytest tests/test_tool_parsing.py > test_output.txt 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed!"
}
