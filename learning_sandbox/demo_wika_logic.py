# === ШАГ 1: Подключаем нужные инструменты (библиотеки) ===
import math  # Математические функции

# === ШАГ 2: Задаем правила (настройки из config.json) ===
test_pressure = 20.0      # Целевое давление: 20 бар
allowed_drop = 0.5        # Максимально допустимое падение: 0.5 бар
lower_limit = test_pressure - allowed_drop  # Нижний порог: 19.5 бар

# === ШАГ 3: Имитируем данные с манометра WIKA CPG1500 (время и давление) ===
# Представим, что мы прочитали это из CSV-файла:
time_minutes = [0, 1, 2, 3, 4, 5]
pressure_bar = [0.0, 20.1, 20.0, 19.8, 19.7, 19.6]  # Давление в каждую минуту

# === ШАГ 4: Логика анализа (бизнес-логика) ===
start_pressure = pressure_bar[1]  # Давление на 1-й минуте (20.1)
end_pressure = pressure_bar[5]    # Давление на 5-й минуте (19.6)
actual_drop = start_pressure - end_pressure  # Падение = 20.1 - 19.6 = 0.5 бар

# === ШАГ 5: Принятие решения (PASS / FAIL) ===
print("--- РЕЗУЛЬТАТ АНАЛИЗА ИСПЫТАНИЯ ---")
print("Начальное давление выдержки: " + str(start_pressure) + " бар")
print("Конечное давление выдержки: " + str(end_pressure) + " бар")
print("Фактическое падение: " + str(round(actual_drop, 2)) + " бар")

if actual_drop <= allowed_drop:
    status = "PASS (ПРОЙДЕНО)"
else:
    status = "FAIL (БРАК)"

print("Итоговый статус испытания: " + status)
