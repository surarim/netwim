#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import winreg, subprocess, sys, os, logging, logging.handlers

# Установка рабочей папки
workdir = os.path.abspath(os.path.dirname(__file__))
os.chdir(workdir)
sys.path.append(workdir)

# Загрузка внутреннего модуля конфигурации
try:
  from install_config import *
except ModuleNotFoundError as err:
  print("Cannot run - " + str(err))
  sys.exit()

#------------------------------------------------------------------------------------------------

# Получение ip адреса клиента
p = subprocess.Popen(["cmd", "/c", "ipconfig"], stdout=subprocess.PIPE)
for line in iter(p.stdout.readline, b''):
  if line.decode('utf-8').find("IPv4") != -1:
    client_ip = line.decode('utf-8').split(":")[1].strip()

# Проверка пользователя по группе в домене Active Directory
def check_user():
  print("Cannot run - current user not allowed"); sys.exit()

# Определение UEFI или BIOS
def pefirmwaretype():
  try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "System\CurrentControlSet\Control")
    value = winreg.QueryValueEx(key, "PEFirmwareType")[0]
    winreg.CloseKey(key)
    if value == 1: return "BIOS"
    if value == 2: return "UEFI"
  except WindowsError:
    return "Unknown"

# Получение версии ACPI (если найдена таблица XSDT - 2.0, иначе 1.0)
def acpi_version():
  path = "HARDWARE\ACPI\RSDT"
  while True:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    try:
      subkey = winreg.EnumKey(key,0)
      if subkey: path = path + "\\" + subkey
      winreg.CloseKey(key)
    except:
      break
  try:
    subvalue = winreg.EnumValue(key,0)[1]
  except:
    pass
  return "2.0" if subvalue and subvalue.find(b"XSDT") != -1 else "1.0"

# Определение разрядности PE образа
def peimagebits():
  return "64" if sys.maxsize > 2**32 else "32"

# Определение возможности установки (проверка CPU и ACPI)
def install_warning(win_ver):
  warning_mes = "\033[1mВнимание!\033[0m Система может не запустится\n          "
  # Проверка CPU
  cpubits = subprocess.run(["cpuid"+peimagebits()],capture_output=True, encoding="utf-8").stdout
  cpu_warning_bits = ""
  if win_ver == "win7" or win_ver == "win10" or win_ver == "win11":
    if cpubits.find("x86_64") == -1: cpu_warning_bits += " x86_64"
    if cpubits.find("PAE") == -1: cpu_warning_bits += " PAE"
    if cpubits.find("NX") == -1: cpu_warning_bits += " NX"
  if win_ver == "win10" or win_ver == "win11":
    if cpubits.find("CMPXCHG16B") == -1: cpu_warning_bits += " CMPXCHG16B"
    if cpubits.find("LAHF/SAHF") == -1: cpu_warning_bits += " LAHF/SAHF"
    if cpubits.find("PREFETCHW") == -1: cpu_warning_bits += " PREFETCHW"
  if win_ver == "win11":
    if cpubits.find("SSE4.1") == -1: cpu_warning_bits += " SSE4.1"
  cpu_warning_mes = warning_mes + "Процессор не поддерживает" + cpu_warning_bits if len(cpu_warning_bits) > 0 else "Процессор поддерживает все необходимые функции"
  # Проверка ACPI
  acpi_warning_bits = ""
  if acpi_version() == "2.0" and win_ver == "winxp":
    acpi_warning_bits = "Операционная система не поддерживает ACPI 2.0 материнской платы"
    acpi_warning_mes = "          " + warning_mes + acpi_warning_bits
  else:
    acpi_warning_mes = "          Операционная система поддерживает ACPI материнской платы"
  # Вывод результата
  return cpu_warning_mes + "\n" + acpi_warning_mes

# Вывод сообщений запущенных процессов
def print_cmd_stdout(process):
  applying_image = False
  for line in iter(process.stdout.readline, b''):
    # Проверка на индикатор прогресс бара (вывод на той же строке)
    if line.decode('utf-8').find("Applying image") != -1:  applying_image = True
    if line.decode('utf-8').find("100.0%") != -1 and applying_image: applying_image = False
    if line.decode('utf-8').find("[") != -1 and applying_image:
      print(line.decode('utf-8').rstrip('\n'), end='\r')
    else:
      # Вывод обычным образом
      print(line.decode('utf-8').rstrip('\n'))

# Установка Windows
def install_win(win_ver):
  subprocess.run(["cmd", "/c", "title "+win_menu[win_menu.index(win_ver)+2]+" (версия "+win_menu[win_menu.index(win_ver)+1]+") и перезагрузка"])

  # Разметка диска и форматирование
  p = subprocess.Popen(["cmd", "/c", "diskpart /s ", workdir+"\\"+win_menu[win_menu.index(win_ver)+3]], stdout=subprocess.PIPE)
  print_cmd_stdout(p)
  log.info("PXE "+client_ip+" Disk completed for install "+win_ver)

  # Установка из wim образа
  if win_ver == "winxp":
    p = subprocess.Popen(["cmd", "/c", "dism /apply-image /imagefile:"+workdir+"\\"+win_ver+"_"+win_menu[win_menu.index(win_ver)+1]+".wim /index:1 /applydir:"+volume1], stdout=subprocess.PIPE)
    print_cmd_stdout(p)
  if win_ver == "win7" or win_ver == "win10" or win_ver == "win11":
    p = subprocess.Popen(["cmd", "/c", "dism /apply-image /imagefile:"+workdir+"\\"+win_ver+"_"+win_menu[win_menu.index(win_ver)+1]+".wim /index:1 /applydir:"+volume2], stdout=subprocess.PIPE)
    print_cmd_stdout(p)
  log.info("PXE "+client_ip+" Applied wim image for "+win_ver)

  # Настройка загрузчика
  if win_ver == "win7":
    p = subprocess.Popen(["cmd", "/c", "bcdboot "+volume2+"\\"+"windows /l ru-RU /s "+volume1+" /f BIOS"], stdout=subprocess.PIPE)
    print_cmd_stdout(p)
  if win_ver == "win10" or win_ver == "win11":
    p = subprocess.Popen(["cmd", "/c", "bcdboot "+volume2+"\\"+"windows /l ru-RU /s "+volume1+" /f all"], stdout=subprocess.PIPE)
    print_cmd_stdout(p)
  if win_ver == "win7" or win_ver == "win10" or win_ver == "win11":
    log.info("PXE "+client_ip+" Bcdboot completed for image "+win_ver)

  # Завершение установки
  print("----------------------------------------------------------------")
  print("Установка завершена, подготовка к перезагрузке")
  p = subprocess.Popen(["cmd", "/c", "ping -n 4 localhost > nul"], stdout=subprocess.PIPE)
  #p = subprocess.Popen(["cmd", "/c", "wpeutil reboot"], stdout=subprocess.PIPE)
  subprocess.run(["cmd", "/c", "pause"])

# Меню
def run_menu():
  subprocess.run(["cmd", "/c", "title Меню установки - ",pefirmwaretype(),peimagebits()])
  log.info("PXE "+client_ip+" Menu running")
  mes=""
  while mes != "0" and mes != "installed":
    # Очистка экрана и вывод шапки
    subprocess.run(["cmd", "/c", "cls"])
    print()
    print("  Порядок работы:")
    print()
    print("      0) Выход в командную строку")
    # Вывод меню и нумерация
    pos = 0
    menu_num = 0
    while pos < len(win_menu):
      # Номер 0 (определить номер пункта автоматически)
      if int(win_menu[pos]) == 0:
        menu_num = menu_num + 1
        win_menu[pos] = str(menu_num)
        print()
        print("      "+str(menu_num)+") "+win_menu[pos+3]+" (версия "+win_menu[pos+2]+")")
        # Вывод дополнительной информации о возможности установки (проверка CPU)
        print("         ("+install_warning(win_menu[pos+1])+")")
      pos = pos + 5
    # Выбор пункта меню
    print()
    print("  Для выбора пункта меню введи соответствующую ему цифру и нажми Enter: ", end = '')
    try:
      mes = input()
    except:
      pass
    # Поиск образа по выбранному номеру и запуск установки
    pos = 0
    while pos < len(win_menu):
      if win_menu[pos] == mes:
        subprocess.run(["cmd", "/c", "cls"])
        log.info("PXE "+client_ip+" Menu selected: "+mes+" "+win_menu[pos+1])
        mes = "installed"
        install_win(win_menu[pos+1])
        break
      pos = pos + 5
  # Завершение работы
  log.info("PXE "+client_ip+" Menu completed")

#------------------------------------------------------------------------------------------------

# Главный модуль программы
if __name__ =='__main__':
  # Проверки перед запуском меню
  # -----------------------------------------------------------------------
  # Введён адрес PXE сервера?
  if len(sys.argv) != 2: print("Usage: install.py <pxe_server>"); sys.exit()
  # Это PE образ?
  if pefirmwaretype()=="Unknown": print("Cannot run - not PE Image"); sys.exit()
  # Указан ip адрес PXE сервера?
  pxe_server = sys.argv[1]
  connect_no = True
  p = subprocess.Popen(["cmd", "/c", "ping -n 2 ", pxe_server], stdout=subprocess.PIPE)
  for line in iter(p.stdout.readline, b''):
    if line.decode('utf-8').find("Lost") != -1 and line.decode('utf-8').split("(")[1].split("%")[0] == "0":
      connect_no = False
      break
  if connect_no: print("Cannot run - no connection to PXE server"); sys.exit()
  # Файлы все на месте?
  if os.path.isfile('cpuid'+peimagebits()+'.exe') == False: print("Cannot run - cpuid"+peimagebits()+" not found"); sys.exit()
  try: subprocess.run(["cpuid"+peimagebits()],capture_output=True, encoding="utf-8").stdout
  except: print("Cannot run - cpuid"+peimagebits()+" error"); sys.exit()
  pos = 0
  import os.path
  while pos < len(win_menu):
    if win_menu[pos] == "0" and os.path.isfile(win_menu[pos+4]) == False: print("Cannot run - file "+win_menu[pos+4]+" not found"); sys.exit()
    if win_menu[pos] == "0" and os.path.isfile(win_menu[pos+1]+"_"+win_menu[pos+2]+".wim") == False: print("Cannot run - file "+win_menu[pos+1]+"_"+win_menu[pos+2]+".wim"+" not found"); sys.exit()
    pos = pos + 5
  # Проверка пользователя по группе в домене Active Directory
  if not ignore_auth: check_user()
  # -----------------------------------------------------------------------
  # Все проверки прошли успешно
  #
  # Настройка логирования на PXE сервер
  log = logging.getLogger('log')
  log.setLevel(logging.INFO)
  log.addHandler(logging.handlers.SysLogHandler(address = (pxe_server,514)))
  # Запуск меню
  run_menu()
