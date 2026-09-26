try:
    age = int(input("请输入年龄："))
    print(age)
except ValueError:
    print("请输入数字")