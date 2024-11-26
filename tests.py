import unittest
import zipfile
import os
from ShellEmulator import ShellEmulator


class TestShellEmulator(unittest.TestCase):

    def setUp(self):
        # Создаем временный тестовый архив
        self.test_zip_path = "test_shell.zip"
        with zipfile.ZipFile(self.test_zip_path, "w") as zip_file:
            zip_file.writestr("root_dir/", "")
            zip_file.writestr("root_dir/file1.txt", "Hello world!")
            zip_file.writestr("root_dir/folder1/", "")
            zip_file.writestr("root_dir/folder1/file2.txt", "Test file")
            zip_file.writestr("root_dir/folder1/file3.txt", "Another test file")

        # Создаем файл конфигурации
        self.config_path = "test_config.csv"
        with open(self.config_path, "w") as config_file:
            config_file.write("test-hostname,test_shell.zip")

        # Инициализируем эмулятор
        self.emulator = ShellEmulator(self.config_path)

    def tearDown(self):
        # Удаляем временные файлы
        os.remove(self.test_zip_path)
        os.remove(self.config_path)

    def test_cd(self):
        # Проверяем переход в корневую директорию
        self.emulator.change_directory("/")
        self.assertEqual(self.emulator.current_dir, "/")

        # Проверяем переход в существующую директорию
        self.emulator.change_directory("folder1")
        self.assertEqual(self.emulator.current_dir, "/folder1/")

        # Проверяем переход на уровень выше
        self.emulator.change_directory("..")
        self.assertEqual(self.emulator.current_dir, "/")

        # Проверяем попытку перехода в несуществующую директорию
        self.emulator.change_directory("nonexistent")
        self.assertEqual(self.emulator.current_dir, "/")  # Остаёмся в текущей директории

    def test_ls(self):
        # Проверяем содержимое корневой директории
        output = self.emulator.list_directory()
        self.assertEqual(output, ["file1.txt", "folder1"])

        # Проверяем содержимое папки folder1
        output = self.emulator.list_directory("folder1")
        self.assertEqual(output, ["file2.txt", "file3.txt"])

        # Проверяем содержимое несуществующей директории
        output = self.emulator.list_directory("nonexistent")
        self.assertEqual(output, [])

    def test_wc(self):
        # Подсчет слов, строк и символов в файле file1.txt
        output = self.emulator.word_count("file1.txt")
        self.assertEqual(output, "0 2 12 file1.txt")

        # Проверка работы флагов
        output = self.emulator.word_count("-l file1.txt")  # Только строки
        self.assertEqual(output, "0 file1.txt")
        output = self.emulator.word_count("-w file1.txt")  # Только слова
        self.assertEqual(output, "2 file1.txt")
        output = self.emulator.word_count("-m file1.txt")  # Только символы
        self.assertEqual(output, "12 file1.txt")

        # Подсчет в несуществующем файле
        output = self.emulator.word_count("nonexistent.txt") # Ожидаем сообщение об ошибке
        self.assertEqual(output, "wc: nonexistent.txt: No such file")

    def test_rm(self):
        # Удаляем файл
        self.emulator.remove_file_or_directory("file1.txt")
        self.assertNotIn("/file1.txt", self.emulator.virtual_files)

        # Попытка удалить директорию без флага -r
        self.emulator.remove_file_or_directory("folder1")
        self.assertIn("/root_dir/folder1", self.emulator.virtual_files)

        # Удаляем папку рекурсивно
        self.emulator.remove_file_or_directory("-r folder1")
        self.assertNotIn("/folder1", self.emulator.virtual_files)

        # Попытка удалить несуществующий файл
        self.emulator.remove_file_or_directory("nonexistent")
        self.assertNotIn("/nonexistent", self.emulator.virtual_files)


if __name__ == "__main__":
    unittest.main()