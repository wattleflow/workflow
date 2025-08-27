# Wattlelfow Workflow Tools - plantuml.py

The tool reads a `source` file, parse it and prints PlantUML text to stdout.

>> NOTE: Currently, only the .sql extension is supported.

## Usage
```bash
python -m tools.plamtuml <path/to/file.sql> [--log-level NOTSET|INFO|DEBUG|WARNING|ERROR]
```
or
```bash
python tools/plamtuml.py <path/to/file.sql> [--log-level INFO]
```

## Examples

- display PlantUML in the terminal
```bash
python -m tools.plamtuml schema.sql
```
- save to .puml and render with PlantUML
```bash
python -m tools.plamtuml schema.sql > schema.puml
plantuml schema.puml  # generates .png/.svg
```

## Linux: install plantuml with conda
- install or build your own VSCode plugin
```bash
code --install-extension plantuml-1.0.0.vsix

# or localy if you have built your own version
code --install-extension ~/plugin/vscode-plantuml/plantuml-1.0.0.vsix
```

- install plantuml graphviz and nodejs (if you'd like to control the plugin yourself.)
```bash
conda install -c conda-forge openjdk=17 graphviz plantuml nodejs
```

## Setting PlantUML in VSCode
code --install-extension plantuml-1.0.0.vsix
#  ili 
code --install-extension ~/projects/plugins/vscode-plantuml/plantuml-1.0.0.vsix
```
- **Must add following to**: `.vscode/setting.json` in your project

```json
    "plantuml.exportFormat": "png",
    "plantuml.render": "Local",
    "plantuml.java": "/home/username/miniconda3/envs/plantuml/bin/java",
    "plantuml.jar": "/home/username/miniconda3/envs/plantuml/lib/plantuml.jar",
    "plantuml.commandArgs": []
```
