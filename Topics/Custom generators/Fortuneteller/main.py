input_number = input()

def get_digit(number):
    for digit in number:
        yield int(digit)

total = sum(get_digit(input_number))

print(total)
