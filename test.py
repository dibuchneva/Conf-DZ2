import requests
import csv
import zipfile
import re
import subprocess
import os
import unittest
from unittest.mock import mock_open, patch


# Основные функции программы

def load_config(path):
    config = {
        "visualizer_path": "",
        "package": "",
        "output": "",
        "max_depth": 2
    }
    with open(path, newline='') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=',')
        for row in spamreader:
            config[row[0]] = row[1]

    return config


def download_nuget_package(nuget_url, path):
    response = requests.get(nuget_url)

    if response.status_code == 200:
        with open(path, 'wb') as f:
            f.write(response.content)
        return path
    else:
        return None

def get_dependencies(package_path):
    dependencies = []
    with zipfile.ZipFile(package_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if file_info.filename.endswith('.nuspec'):
                with zip_ref.open(file_info) as nuspec_file:
                    nuspec_content = nuspec_file.read()
                    dependencies = parse_nuspec(nuspec_content)
                break
    return dependencies


def parse_nuspec(nuspec_content):
    nuspec_text = nuspec_content.decode('utf-8')

    dependency_pattern = r'<dependency id="([^"]+)"'
    dependencies = re.findall(dependency_pattern, nuspec_text)

    return set(dependencies)


def generate_dot_graph(package_name, dependencies):
    dot = 'digraph G {\n'
    dot += '    graph [layout=neato, overlap=false, splines=true];\n'
    dot += f'    "{package_name}"\n'
    for dep in dependencies:
        dot += f'    "{dep}" -> "{package_name}";\n'
    dot += '}'
    return dot


def visualize_graph(visualizer_path, dot_graph, output_path):
    file_path = os.path.join(os.getcwd(), 'graph.dot')
    with open(file_path, 'w', encoding='utf-8') as dot_file:
        dot_file.write(dot_graph)

    output_png = os.path.join(os.getcwd(), output_path)
    subprocess.run([visualizer_path, '-Tpng', file_path, '-o', output_png], check=True)

    print(f"Граф зависимостей сохранен в: {output_png}")


def download_and_get_deps(url, path, deps, depth, max_depth):
    if depth > max_depth:
        return deps
    if depth > 0:
        package_name = str(url.split("/")[6])
        print(f"[i] Скачиваю пакет {package_name} для анализа зависимостей")
        download_nuget_package(url, path)
    dependencies = get_dependencies(path)
    for dep in dependencies:
        if dep in deps:
            continue
        deps.append(dep)
        download_and_get_deps(f"https://www.nuget.org/api/v2/package/{dep}", 
                              "./temp/package.nupkg", deps, depth + 1, max_depth)
    return deps


# Тесты для программы

class TestLoadConfig(unittest.TestCase):
    @patch("builtins.open", mock_open(read_data="package,test-package\noutput,output.png\nmax_depth,3"))
    def test_load_config(self):
        config = load_config("dummy_path.csv")
        self.assertEqual(config["package"], "test-package")
        self.assertEqual(config["output"], "output.png")
        self.assertEqual(config["max_depth"], "3")

    @patch("builtins.open", mock_open(read_data=""))
    def test_empty_config(self):
        config = load_config("dummy_path.csv")
        self.assertEqual(config["package"], "")
        self.assertEqual(config["output"], "")
        self.assertEqual(config["max_depth"], "2")


class TestDownloadNugetPackage(unittest.TestCase):
    @patch("requests.get")
    def test_download_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"dummy package content"
        
        result = download_nuget_package("https://example.com/package", "dummy_path.nupkg")
        self.assertEqual(result, "dummy_path.nupkg")
        with open("dummy_path.nupkg", "rb") as f:
            content = f.read()
        self.assertEqual(content, b"dummy package content")
        
    @patch("requests.get")
    def test_download_failure(self, mock_get):
        mock_get.return_value.status_code = 404
        
        result = download_nuget_package("https://example.com/package", "dummy_path.nupkg")
        self.assertIsNone(result)


class TestGetDependencies(unittest.TestCase):
    @patch("zipfile.ZipFile")
    def test_get_dependencies(self, mock_zip):
        mock_zip.return_value.__enter__.return_value.infolist.return_value = [
            zipfile.ZipInfo("package.nuspec"),
        ]
        mock_zip.return_value.__enter__.return_value.open.return_value.read.return_value = b'''
        <package>
            <metadata>
                <dependencies>
                    <dependency id="Dependency1" />
                    <dependency id="Dependency2" />
                </dependencies>
            </metadata>
        </package>
        '''

        dependencies = get_dependencies("dummy_path.nupkg")
        self.assertIn("Dependency1", dependencies)
        self.assertIn("Dependency2", dependencies)


class TestGenerateDotGraph(unittest.TestCase):
    def test_generate_dot_graph(self):
        dependencies = {"Dep1", "Dep2"}
        dot_graph = generate_dot_graph("TestPackage", dependencies)
        
        expected_dot = '''digraph G {
    graph [layout=neato, overlap=false, splines=true];
    "TestPackage"
    "Dep1" -> "TestPackage";
    "Dep2" -> "TestPackage";
}'''
        
        self.assertEqual(dot_graph, expected_dot)


class TestVisualizeGraph(unittest.TestCase):
    @patch("subprocess.run")
    def test_visualize_graph(self, mock_run):
        mock_run.return_value = None
        
        visualizer_path = "dummy/path/to/visualizer"
        dot_graph = '''digraph G {
    "Package"
    "Dependency" -> "Package";
}'''
        output_path = "output.png"
        
        visualize_graph(visualizer_path, dot_graph, output_path)
        
        mock_run.assert_called_with([visualizer_path, '-Tpng', 'graph.dot', '-o', 'output.png'], check=True)


class TestDownloadAndGetDeps(unittest.TestCase):
    @patch("requests.get")
    @patch("zipfile.ZipFile")
    def test_download_and_get_deps(self, mock_zip, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"dummy package content"
        
        mock_zip.return_value.__enter__.return_value.infolist.return_value = [
            zipfile.ZipInfo("package.nuspec"),
        ]
        mock_zip.return_value.__enter__.return_value.open.return_value.read.return_value = b'''
        <package>
            <metadata>
                <dependencies>
                    <dependency id="Dep1" />
                </dependencies>
            </metadata>
        </package>
        '''

        deps = download_and_get_deps("https://www.nuget.org/api/v2/package/TestPackage", 
                                     "dummy_path.nupkg", [], 0, 2)
        self.assertIn("Dep1", deps)
        self.assertEqual(len(deps), 1)


if __name__ == '__main__':
    unittest.main()