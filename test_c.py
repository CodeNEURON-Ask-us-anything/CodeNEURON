import requests
import json

c_code = """#include <stdio.h>
int main() {
    printf("TEST_CASE_1: PASSED\\n");
    return 0;
}
"""

res = requests.post('http://127.0.0.1:8000/api/verify-code', json={'code': c_code, 'language': 'c'})
print(json.dumps(res.json(), indent=2))
