def divide(a, b):
    if b == 0:
        return 'Error: Division by zero'
    return a / b

if __name__ == '__main__':
    print(divide(10, 2))
    print(divide(10, 0))