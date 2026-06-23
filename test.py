from code_verification.router import verify_code_chunk

chunk = {
    "type": "code",
    "language": "c",
    "content": """int main() {
    int arr[] = {38, 27, 43, 3, 9, 82, 10};
    int n = sizeof(arr) / sizeof(arr[0])intf("Sorted array: ");
    for (int i = 0; i < n; i++)
        printf("%d ", arr[i]);

    return 0;
}"""
}

res = verify_code_chunk(chunk)
print(res)
