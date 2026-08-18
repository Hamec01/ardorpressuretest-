import random

# 1. Знакомимся с игроком
name = input('Введите ваше имя: ')
print('Привет, ' + name + '!')

# 2. Компьютер загадывает секретное число от 1 до 10
secret_number = random.randint(1, 10)

# 3. Спрашиваем вариант у игрока и переводим текст в число
user_guess = int(input('Угадай число от 1 до 10: '))

# 4. Проверяем результат
if user_guess == secret_number:
    print('Поздравляю, ' + name + '! Вы угадали!')
else:
    print('Ответ неверный! Я загадал число ' + str(secret_number))
