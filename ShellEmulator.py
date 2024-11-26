import os
import zipfile
from tempfile import NamedTemporaryFile

import pyzipper
import csv
import sys


class ShellEmulator:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.hostname = self.config['hostname']
        self.zip_path = self.config['zip_file']
        self.current_dir = "/"  # Начальная директория для пользователя
        self.root_dir = None  # Имя корневой папки архива
        self.virtual_files = self.load_zip()

    def load_config(self, config_path):
        """Загрузка конфигурации из CSV."""
        with open(config_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        return {
            'hostname': rows[0][0],
            'zip_file': rows[0][1],
        }

    def load_zip(self):
        """Загрузка содержимого zip-файла."""
        virtual_files = {}
        with zipfile.ZipFile(self.zip_path, 'r') as zip_file:
            for name in zip_file.namelist():
                normalized_name = "/" + name.rstrip('/')
                if name.endswith('/'):
                    virtual_files[normalized_name] = None
                else:
                    virtual_files[normalized_name] = zip_file.getinfo(name)

            # Определяем корневую директорию архива
            root_dirs = {name.split('/')[0] for name in zip_file.namelist() if '/' in name}
            if len(root_dirs) == 1:
                self.root_dir = f"/{list(root_dirs)[0]}"
            else:
                raise ValueError("Архив должен содержать только одну корневую папку.")

        return virtual_files

    def map_to_real_path(self, path):
        """Добавляет root_dir к указанному пути."""
        if path == "/":
            return self.root_dir
        return self.root_dir + path

    def execute_command(self, command):
        """Выполнение команды."""
        if command.startswith("cd"):
            self.change_directory(command.split(" ")[1] if len(command.split(" ")) > 1 else "/")
        elif command.startswith("ls"):
            self.list_directory(command.split(" ")[1] if len(command.split(" ")) > 1 else "")
        elif command == "exit":
            self.exit_shell()
        elif command.startswith("wc"):
            args = command[3:].strip()
            self.word_count(args)
        elif command.startswith("rm"):
            args = command[3:].strip()
            self.remove_file_or_directory(args)
        else:
            print(f"{command}: command not found")

    def change_directory(self, path):
        """Команда cd: смена директории."""

        if path == "/":
            # Переход в корень
            self.current_dir = "/"
            return
        elif path == "..":
            # Переход на уровень вверх
            if self.current_dir != "/":
                self.current_dir = '/'.join(self.current_dir.rstrip('/').split('/')[:-1])
                if not self.current_dir.startswith("/"):
                    self.current_dir = "/" + self.current_dir
            if not self.current_dir.endswith("/"):
                self.current_dir += "/"
            return
        elif not path.startswith("/"):
            # Если путь относительный, создаём полный пользовательский путь
            path = self.current_dir.rstrip('/') + '/' + path

        # Проверяем, существует ли директория в архиве
        real_path = self.map_to_real_path(path)
        if real_path in self.virtual_files and self.virtual_files[real_path] is None:
            # Переход в указанную директорию
            self.current_dir = path.rstrip('/') + "/"
        else:
            print(f"cd: {path}: No such file or directory")

    def list_directory(self, path=""):
        """Команда ls: отображение содержимого директории."""
        # Определяем реальный путь: либо переданный, либо текущий
        user_path = self.current_dir + path if path else self.current_dir
        real_path = self.map_to_real_path(user_path).rstrip('/')

        # Проверяем, существует ли директория
        if real_path not in self.virtual_files or (
                real_path in self.virtual_files and self.virtual_files[real_path] is not None):
            print(f"ls: {path}: No such file or directory")
            return []

        # Содержимое директории
        dir_path = real_path + "/"
        dir_content = [
            name[len(dir_path):].split('/')[0]
            for name in self.virtual_files
            if name.startswith(dir_path) and name != dir_path
        ]

        # Убираем дубликаты и сортируем
        dir_content = sorted(set(dir_content))

        # Выводим содержимое директории
        print("\n".join(dir_content))
        return dir_content

    def get_file_content(self, path):
        """Получение содержимого файла из zip."""
        with zipfile.ZipFile(self.zip_path, "r") as zip_file:
            return zip_file.read(path.lstrip("/"))

    def word_count(self, args):
        """Команда wc: подсчёт строк, слов и символов в файле."""
        # Разделяем аргументы на части
        parts = args.split()
        flags = ""
        file_path = None

        # Ищем флаги и имя файла
        while parts:
            part = parts.pop(0)
            if part.startswith("-"):
                flags += part[1:]
            else:
                file_path = part
                break

        # Если имя файла не найдено, выводим ошибку
        if not file_path:
            print("wc: missing file operand")
            return

        # Убираем повторяющиеся флаги и проверяем их корректность
        flags = "".join(sorted(set(flags)))  # Убираем повторы и сортируем
        valid_flags = "lwm"
        for flag in flags:
            if flag not in valid_flags:
                print(f"wc: invalid option -- '{flag}'")
                return

        # Определяем реальный путь
        real_path = self.map_to_real_path(self.current_dir + file_path)

        # Проверяем, существует ли файл
        if real_path not in self.virtual_files or self.virtual_files[real_path] is None:
            print(f"wc: {file_path}: No such file")
            return f"wc: {file_path}: No such file"

        # Получаем содержимое файла
        try:
            content = self.get_file_content(real_path).decode("utf-8")
        except Exception as e:
            print(f"wc: {file_path}: Unable to read file - {str(e)}")
            return f"wc: {file_path}: Unable to read file - {str(e)}"

        # Подсчёт строк, слов и символов
        lines = content.count("\n")
        words = len(content.split())
        chars = len(content)

        # Формируем вывод на основе флагов
        output = []
        if not flags or "l" in flags:
            output.append(str(lines))
        if not flags or "w" in flags:
            output.append(str(words))
        if not flags or "m" in flags:
            output.append(str(chars))

        # Добавляем путь к файлу в конце
        output.append(file_path)
        print(" ".join(output))
        return " ".join(output)

    def remove_from_zip(self, zip_file_path, items_to_remove):
        """Удаляет файлы из ZIP-архива."""
        # Создаем временный файл для нового архива
        temp_file = NamedTemporaryFile(delete=False)
        try:
            with pyzipper.AESZipFile(zip_file_path, 'r') as zip_read:
                # Получаем список всех файлов в архиве
                all_files = zip_read.namelist()

                # Фильтруем файлы для сохранения
                files_to_keep = [f for f in all_files if f.strip('/') not in items_to_remove]

                # Открываем временный архив для записи
                with pyzipper.AESZipFile(temp_file.name, 'w') as zip_write:
                    for file in files_to_keep:
                        # Читаем содержимое файла и записываем в новый архив
                        zip_write.writestr(file, zip_read.read(file))

            # Закрываем временный файл перед заменой
            temp_file.close()

            # Заменяем старый архив новым
            os.replace(temp_file.name, zip_file_path)

        except Exception as e:
            print(f"Error during file removal: {e}")
        finally:
            # Удаляем временный файл, если что-то пошло не так
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except PermissionError:
                    pass  # Файл уже используется или удален

    def remove_file_or_directory(self, args):
        """Команда rm: удаление файла или директории."""
        # Разделяем аргументы на части
        parts = args.split()
        flags = ""
        path = None

        # Ищем флаги и имя файла
        while parts:
            part = parts.pop(0)
            if part.startswith("-"):
                flags += part[1:]
            else:
                path = part
                break

        # Если имя файла не найдено, выводим ошибку
        if not path:
            print("rm: missing file operand")
            return

        # Убираем повторяющиеся флаги и проверяем их корректность
        flags = "".join(sorted(set(flags)))  # Убираем повторы и сортируем
        valid_flags = "r"
        for flag in flags:
            if flag not in valid_flags:
                print(f"rm: invalid option -- '{flag}'")
                return

        recursive = "r" in flags

        # Путь к удаляемому объекту
        full_path = self.map_to_real_path(self.current_dir + path).rstrip('/')

        # Если путь не существует, выводим ошибку
        if full_path not in self.virtual_files:
            print(f"rm: {path}: No such file or directory")
            return

        # Если это файл, удаляем его
        if self.virtual_files[full_path] is not None:
            self.remove_from_zip(self.zip_path, [full_path.lstrip('/')])
            # Удаляем файл из virtual_files
            del self.virtual_files[full_path]
            return

        # Если это директория, проверяем её содержимое
        if self.virtual_files[full_path] is None:
            if not recursive:
                print(f"rm: {path} is a directory. Use -r to remove.")
                return
            # Удаляем директорию
            directory_to_delete = path.split('/')[-1]
            items_to_remove = [item.strip('/') for item in self.virtual_files if directory_to_delete in item]
            self.remove_from_zip(self.zip_path, items_to_remove)
            # Удаляем директорию из virtual_files
            for item in items_to_remove:
                if "/" + item in self.virtual_files:
                    del self.virtual_files["/" + item]
            return

    def exit_shell(self):
        """Команда exit: выход из эмулятора."""
        print("Exiting shell...")
        sys.exit()

    def run(self):
        """Запуск эмулятора."""
        while True:
            command = input(f"{self.hostname}:{self.current_dir if self.current_dir == '/' else self.current_dir[:-1]}$ ")
            self.execute_command(command)


if __name__ == "__main__":
    emulator = ShellEmulator("config.csv")
    emulator.run()