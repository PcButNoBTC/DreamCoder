"""Project generator + self-heal.

Generates multi-file projects from a natural-language brief (any language),
and proposes fixes when builds/runs fail.
"""

from __future__ import annotations

import json
import re
import time
import zipfile
from io import BytesIO
from typing import Any
from pathlib import Path


def _detect_stack(prompt: str) -> dict[str, str]:
    p = prompt.lower()
    if any(k in p for k in ("c++", "cpp", "visual studio", "win32", "mfc", "qt ", "imgui")):
        return {"language": "cpp", "kind": "desktop", "build": "cmake"}
    if re.search(r"\bc\b", p) and "c++" not in p and "cpp" not in p:
        return {"language": "c", "kind": "cli", "build": "make"}
    if any(k in p for k in ("rust", "cargo")):
        return {"language": "rust", "kind": "cli", "build": "cargo"}
    if any(k in p for k in ("go ", "golang")):
        return {"language": "go", "kind": "cli", "build": "go"}
    if any(k in p for k in ("typescript", "react", "next.js", "node", "javascript", "vue", "svelte")):
        return {"language": "typescript", "kind": "web", "build": "npm"}
    if any(k in p for k in ("java", "spring", "maven", "gradle")):
        return {"language": "java", "kind": "app", "build": "maven"}
    if any(k in p for k in ("c#", "csharp", ".net", "winforms", "wpf")):
        return {"language": "csharp", "kind": "desktop", "build": "dotnet"}
    if any(k in p for k in ("html", "css", "static site", "landing")):
        return {"language": "html", "kind": "web", "build": "static"}
    return {"language": "python", "kind": "app", "build": "pip"}


def _slug(prompt: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", prompt.lower())[:4]
    return "-".join(words) or "generated-app"


def generate_project(prompt: str, project_goal: str = "") -> dict[str, Any]:
    """Return a full multi-file project from a brief."""
    start = time.perf_counter()
    stack = _detect_stack(prompt)
    name = _slug(prompt)
    goal = project_goal or prompt.strip()[:200]
    files: list[dict[str, str]] = []
    pages: list[dict[str, str]] = []  # logical "pages" / steps for the UI wizard

    lang = stack["language"]

    if lang == "python":
        files = _gen_python(name, prompt, goal)
    elif lang == "cpp":
        files = _gen_cpp(name, prompt, goal)
    elif lang == "c":
        files = _gen_c(name, prompt, goal)
    elif lang == "typescript":
        files = _gen_ts(name, prompt, goal)
    elif lang == "html":
        files = _gen_html(name, prompt, goal)
    elif lang == "csharp":
        files = _gen_csharp(name, prompt, goal)
    elif lang == "rust":
        files = _gen_rust(name, prompt, goal)
    elif lang == "go":
        files = _gen_go(name, prompt, goal)
    elif lang == "java":
        files = _gen_java(name, prompt, goal)
    else:
        files = _gen_python(name, prompt, goal)

    # Logical generation pages for the wizard
    pages = [
        {"id": "plan", "title": "Plan", "detail": f"Stack: {lang} / {stack['kind']} / {stack['build']}"},
        {"id": "scaffold", "title": "Scaffold", "detail": f"{len(files)} files planned"},
        {"id": "implement", "title": "Implement", "detail": "Core logic and entrypoints"},
        {"id": "debug", "title": "Debug hooks", "detail": "Error paths, logging, sanity checks"},
        {"id": "package", "title": "Package", "detail": "README + run instructions + zip"},
    ]

    readme = next((f for f in files if f["path"].lower().endswith("readme.md")), None)
    latency = int((time.perf_counter() - start) * 1000) + 40
    return {
        "name": name,
        "prompt": prompt,
        "goal": goal,
        "stack": stack,
        "files": files,
        "pages": pages,
        "file_count": len(files),
        "latency_ms": latency,
        "summary": f"Generated {len(files)}-file {lang} project “{name}”",
        "run_hint": _run_hint(stack, name),
        "self_heal_ready": True,
        "source": "template",
    }


def _run_hint(stack: dict, name: str) -> str:
    b = stack["build"]
    if b == "pip":
        return f"cd {name} && pip install -r requirements.txt && python main.py"
    if b == "cmake":
        return f"cd {name} && mkdir build && cd build && cmake .. && cmake --build ."
    if b == "make":
        return f"cd {name} && make && ./app"
    if b == "npm":
        return f"cd {name} && npm install && npm start"
    if b == "dotnet":
        return f"cd {name} && dotnet run"
    if b == "cargo":
        return f"cd {name} && cargo run"
    if b == "go":
        return f"cd {name} && go run ."
    if b == "maven":
        return f"cd {name} && mvn -q package && java -jar target/*.jar"
    return f"See {name}/README.md"


def _infer_app_spec(prompt: str) -> dict[str, Any]:
    text = (prompt or "").lower()
    if any(k in text for k in ("todo", "task", "checklist", "kanban", "reminder")):
        return {
            "kind": "task_manager",
            "title": "Task manager",
            "entity": "Task",
            "item_name": "task",
            "summary": "task tracking and daily follow-through",
            "operations": ["add_task", "complete_task", "list_tasks", "summary"],
        }
    if any(k in text for k in ("budget", "expense", "finance", "money", "wallet")):
        return {
            "kind": "budget_tracker",
            "title": "Budget tracker",
            "entity": "Expense",
            "item_name": "expense",
            "summary": "spending and monthly summaries",
            "operations": ["add_expense", "monthly_summary", "list_expenses", "budget_remaining"],
        }
    if any(k in text for k in ("note", "journal", "memo", "writing", "idea")):
        return {
            "kind": "notes_app",
            "title": "Notes workspace",
            "entity": "Note",
            "item_name": "note",
            "summary": "capture and search ideas",
            "operations": ["add_note", "search_notes", "list_notes", "delete_note"],
        }
    if any(k in text for k in ("chat", "assistant", "agent", "bot")):
        return {
            "kind": "chat_app",
            "title": "Conversation assistant",
            "entity": "Message",
            "item_name": "message",
            "summary": "conversation memory and quick actions",
            "operations": ["add_message", "list_messages", "reply", "summary"],
        }
    return {
        "kind": "idea_app",
        "title": "Idea workspace",
        "entity": "Idea",
        "item_name": "idea",
        "summary": "turn raw concepts into a plan",
        "operations": ["add_idea", "prioritize_ideas", "list_ideas", "build_report"],
    }


def _gen_python(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    spec = _infer_app_spec(prompt)
    kind = spec["kind"]

    readme = f'''# {name}

{goal}

This project implements a working {spec['title'].lower()} for the idea: "{prompt[:180]}".

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --list
```
'''

    if kind == "task_manager":
        service_code = '''from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    title: str
    priority: str = "medium"
    completed: bool = False
    tags: list[str] = field(default_factory=list)


class TaskManager:
    def __init__(self, project_name: str = "generated-app") -> None:
        self.project_name = project_name
        self.tasks: list[Task] = []

    def add_task(self, title: str, priority: str = "medium", tags: list[str] | None = None) -> Task:
        clean_title = (title or "").strip()
        if not clean_title:
            raise ValueError("task title is required")
        task = Task(title=clean_title, priority=priority, tags=list(tags or []))
        self.tasks.append(task)
        return task

    def complete_task(self, index: int) -> Task:
        if index < 0 or index >= len(self.tasks):
            raise IndexError("task index out of range")
        self.tasks[index].completed = True
        return self.tasks[index]

    def list_tasks(self) -> list[dict[str, Any]]:
        return [{
            "title": task.title,
            "priority": task.priority,
            "completed": task.completed,
            "tags": task.tags,
        } for task in self.tasks]

    def summary(self) -> dict[str, Any]:
        completed = sum(1 for task in self.tasks if task.completed)
        pending = len(self.tasks) - completed
        return {"project_name": self.project_name, "total": len(self.tasks), "completed": completed, "pending": pending}

    def build_report(self) -> str:
        summary = self.summary()
        return f"{self.project_name} status: {summary['total']} total, {summary['pending']} pending, {summary['completed']} completed"
'''
        main_code = '''from __future__ import annotations
import argparse

from app.service import TaskManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Task manager")
    parser.add_argument("--list", action="store_true", help="show tasks")
    parser.add_argument("--add", help="add a task")
    parser.add_argument("--priority", default="medium", help="priority level")
    args = parser.parse_args()

    app = TaskManager(project_name="generated-app")
    if args.add:
        app.add_task(args.add, priority=args.priority)
        print(f"Added {args.add}")
    if args.list:
        print(app.build_report())
        for task in app.list_tasks():
            print(task)
        return
    print(app.build_report())


if __name__ == "__main__":
    main()
'''
        test_code = '''from app.service import TaskManager


def test_add_and_complete_task():
    app = TaskManager(project_name="demo")
    app.add_task("Write release notes", priority="high")
    app.complete_task(0)
    summary = app.summary()
    assert summary["total"] == 1
    assert summary["completed"] == 1
'''
    elif kind == "budget_tracker":
        service_code = '''from __future__ import annotations
from typing import Any


class Expense:
    def __init__(self, title: str, amount: float, category: str = "general") -> None:
        self.title = title
        self.amount = float(amount)
        self.category = category


class BudgetTracker:
    def __init__(self, project_name: str = "generated-app") -> None:
        self.project_name = project_name
        self.expenses: list[Expense] = []

    def add_expense(self, title: str, amount: float, category: str = "general") -> Expense:
        expense = Expense(title=title, amount=amount, category=category)
        self.expenses.append(expense)
        return expense

    def list_expenses(self) -> list[dict[str, Any]]:
        return [{"title": item.title, "amount": item.amount, "category": item.category} for item in self.expenses]

    def monthly_summary(self) -> dict[str, float]:
        total = sum(item.amount for item in self.expenses)
        return {"total": total, "budget_remaining": max(0.0, 1000.0 - total)}

    def build_report(self) -> str:
        summary = self.monthly_summary()
        return f"{self.project_name} spent {summary['total']} this month; remaining budget {summary['budget_remaining']}"
'''
        main_code = '''from __future__ import annotations
import argparse

from app.service import BudgetTracker


def main() -> None:
    parser = argparse.ArgumentParser(description="Budget tracker")
    parser.add_argument("--add", nargs=2, metavar=("TITLE", "AMOUNT"), help="add an expense")
    parser.add_argument("--list", action="store_true", help="show expenses")
    args = parser.parse_args()

    app = BudgetTracker(project_name="generated-app")
    if args.add:
        title, amount = args.add
        app.add_expense(title, float(amount))
    if args.list:
        print(app.build_report())
        for expense in app.list_expenses():
            print(expense)
        return
    print(app.build_report())


if __name__ == "__main__":
    main()
'''
        test_code = '''from app.service import BudgetTracker


def test_budget_summary():
    app = BudgetTracker(project_name="demo")
    app.add_expense("Groceries", 80.0, category="food")
    summary = app.monthly_summary()
    assert summary["total"] == 80.0
    assert summary["budget_remaining"] <= 1000.0
'''
    elif kind == "notes_app":
        service_code = '''from __future__ import annotations
from typing import Any


class Note:
    def __init__(self, title: str, body: str = "") -> None:
        self.title = title
        self.body = body


class NotesWorkspace:
    def __init__(self, project_name: str = "generated-app") -> None:
        self.project_name = project_name
        self.notes: list[Note] = []

    def add_note(self, title: str, body: str = "") -> Note:
        note = Note(title=title, body=body)
        self.notes.append(note)
        return note

    def list_notes(self) -> list[dict[str, Any]]:
        return [{"title": note.title, "body": note.body} for note in self.notes]

    def search_notes(self, query: str) -> list[dict[str, Any]]:
        q = (query or "").lower()
        return [note for note in self.list_notes() if q in note["title"].lower() or q in note["body"].lower()]

    def delete_note(self, index: int) -> None:
        if index < 0 or index >= len(self.notes):
            raise IndexError("note index out of range")
        del self.notes[index]

    def build_report(self) -> str:
        return f"{self.project_name} has {len(self.notes)} notes"
'''
        main_code = '''from __future__ import annotations
import argparse

from app.service import NotesWorkspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Notes workspace")
    parser.add_argument("--add", nargs=2, metavar=("TITLE", "BODY"), help="add a note")
    parser.add_argument("--list", action="store_true", help="show notes")
    parser.add_argument("--search", help="search by text")
    args = parser.parse_args()

    app = NotesWorkspace(project_name="generated-app")
    if args.add:
        title, body = args.add
        app.add_note(title, body)
    if args.search:
        print(app.search_notes(args.search))
    if args.list:
        print(app.build_report())
        for note in app.list_notes():
            print(note)
        return
    print(app.build_report())


if __name__ == "__main__":
    main()
'''
        test_code = '''from app.service import NotesWorkspace


def test_note_search():
    app = NotesWorkspace(project_name="demo")
    app.add_note("Ship beta release")
    results = app.search_notes("release")
    assert results and results[0]["title"].lower().startswith("ship")
'''
    elif kind == "chat_app":
        service_code = '''from __future__ import annotations
from typing import Any


class ConversationAssistant:
    def __init__(self, project_name: str = "generated-app") -> None:
        self.project_name = project_name
        self.messages: list[dict[str, str]] = []

    def add_message(self, text: str, role: str = "user") -> dict[str, str]:
        item = {"text": text, "role": role}
        self.messages.append(item)
        return item

    def list_messages(self) -> list[dict[str, str]]:
        return list(self.messages)

    def reply(self, text: str) -> dict[str, str]:
        return {"text": text, "role": "assistant"}

    def summary(self) -> dict[str, Any]:
        return {"project_name": self.project_name, "message_count": len(self.messages)}

    def build_report(self) -> str:
        return f"{self.project_name} has {len(self.messages)} messages"
'''
        main_code = '''from __future__ import annotations
import argparse

from app.service import ConversationAssistant


def main() -> None:
    parser = argparse.ArgumentParser(description="Conversation assistant")
    parser.add_argument("--add", help="add a user message")
    parser.add_argument("--reply", help="generate a response")
    args = parser.parse_args()

    app = ConversationAssistant(project_name="generated-app")
    if args.add:
        app.add_message(args.add)
    if args.reply:
        print(app.reply(args.reply))
    print(app.build_report())


if __name__ == "__main__":
    main()
'''
        test_code = '''from app.service import ConversationAssistant


def test_message_flow():
    app = ConversationAssistant(project_name="demo")
    app.add_message("hello")
    response = app.reply("How are you?")
    assert response["role"] == "assistant"
'''
    else:
        service_code = '''from __future__ import annotations
from typing import Any


class Idea:
    def __init__(self, title: str, priority: str = "medium") -> None:
        self.title = title
        self.priority = priority
        self.completed = False


class IdeaWorkspace:
    def __init__(self, project_name: str = "generated-app") -> None:
        self.project_name = project_name
        self.ideas: list[Idea] = []

    def add_idea(self, title: str, priority: str = "medium") -> Idea:
        idea = Idea(title=title, priority=priority)
        self.ideas.append(idea)
        return idea

    def list_ideas(self) -> list[dict[str, Any]]:
        return [{"title": idea.title, "priority": idea.priority, "completed": idea.completed} for idea in self.ideas]

    def prioritize_ideas(self) -> list[dict[str, Any]]:
        return sorted(self.list_ideas(), key=lambda item: (item["completed"], item["priority"]))

    def build_report(self) -> str:
        return f"{self.project_name} has {len(self.ideas)} ideas"
'''
        main_code = '''from __future__ import annotations
import argparse

from app.service import IdeaWorkspace


def main() -> None:
    parser = argparse.ArgumentParser(description="Idea workspace")
    parser.add_argument("--add", help="add an idea")
    parser.add_argument("--list", action="store_true", help="show ideas")
    args = parser.parse_args()

    app = IdeaWorkspace(project_name="generated-app")
    if args.add:
        app.add_idea(args.add)
    if args.list:
        print(app.build_report())
        for idea in app.list_ideas():
            print(idea)
        return
    print(app.build_report())


if __name__ == "__main__":
    main()
'''
        test_code = '''from app.service import IdeaWorkspace


def test_idea_flow():
    app = IdeaWorkspace(project_name="demo")
    app.add_idea("Launch MVP")
    report = app.build_report()
    assert "demo" in report
'''

    return [
        {"path": f"{name}/README.md", "content": readme},
        {"path": f"{name}/requirements.txt", "content": ""},
        {"path": f"{name}/main.py", "content": main_code},
        {"path": f"{name}/app/__init__.py", "content": '"""Application package."""\n\n__version__ = "0.1.0"\n'},
        {"path": f"{name}/app/service.py", "content": service_code},
        {"path": f"{name}/tests/test_app.py", "content": test_code},
    ]


def _gen_cpp(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    """C++ desktop-style scaffold (CMake) – forms/UI stub."""
    return [
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\n{goal}\n\nC++ / CMake scaffold (Visual Studio–friendly).\n\n## Build\n```bash\nmkdir build && cd build\ncmake ..\ncmake --build .\n```\n\nOpen the folder in Visual Studio as a CMake project.\n",
        },
        {
            "path": f"{name}/CMakeLists.txt",
            "content": f"""cmake_minimum_required(VERSION 3.16)
project({name.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(app src/main.cpp src/app.cpp src/app.h)
if(MSVC)
  target_compile_options(app private /W4)
else()
  target_compile_options(app private -Wall -Wextra)
endif()
""",
        },
        {
            "path": f"{name}/src/main.cpp",
            "content": f'''#include "app.h"
#include <iostream>
#include <stdexcept>

int main() {{
    try {{
        App app("{goal[:80]}");
        return app.run();
    }} catch (const std::exception& ex) {{
        std::cerr << "[fatal] " << ex.what() << std::endl;
        // Self-heal hint: capture this message in DreamCoder and request a fix
        return 1;
    }}
}}
''',
        },
        {
            "path": f"{name}/src/app.h",
            "content": '''#pragma once
#include <string>

class App {
public:
    explicit App(std::string goal);
    int run();
private:
    std::string goal_;
    void draw_form_stub();  // placeholder for GUI forms (Qt/Win32/etc.)
    void validate() const;
};
''',
        },
        {
            "path": f"{name}/src/app.cpp",
            "content": f'''#include "app.h"
#include <iostream>
#include <stdexcept>

App::App(std::string goal) : goal_(std::move(goal)) {{}}

void App::validate() const {{
    if (goal_.empty()) throw std::invalid_argument("goal required");
}}

void App::draw_form_stub() {{
    // Hypothetical forms surface – replace with Qt, wx, or Win32 dialogs
    std::cout << "==== " << goal_ << " ====\\n";
    std::cout << "[Form] Title: Sample window\\n";
    std::cout << "[Form] Button: OK\\n";
}}

int App::run() {{
    validate();
    draw_form_stub();
    std::cout << "App running. Prompt was related to: {prompt[:60]}\\n";
    return 0;
}}
''',
        },
    ]


def _gen_c(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    return [
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\n{goal}\n\n```bash\nmake\n./app\n```\n",
        },
        {
            "path": f"{name}/Makefile",
            "content": "CC=gcc\nCFLAGS=-Wall -Wextra -std=c11\napp: src/main.c src/app.c\n\t$(CC) $(CFLAGS) -o app src/main.c src/app.c\nclean:\n\trm -f app\n",
        },
        {
            "path": f"{name}/src/main.c",
            "content": f'''#include "app.h"
#include <stdio.h>

int main(void) {{
    int rc = app_run("{goal[:60]}");
    if (rc != 0) {{
        fprintf(stderr, "app failed with code %d\\n", rc);
    }}
    return rc;
}}
''',
        },
        {
            "path": f"{name}/src/app.h",
            "content": "#pragma once\nint app_run(const char *goal);\n",
        },
        {
            "path": f"{name}/src/app.c",
            "content": '''#include "app.h"
#include <stdio.h>
#include <string.h>

int app_run(const char *goal) {
    if (!goal || !goal[0]) {
        fprintf(stderr, "error: empty goal\\n");
        return 1;
    }
    printf("goal: %s\\n", goal);
    return 0;
}
''',
        },
    ]


def _gen_ts(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    return [
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\n{goal}\n\n```bash\nnpm install\nnpm start\n```\n",
        },
        {
            "path": f"{name}/package.json",
            "content": json.dumps(
                {
                    "name": name,
                    "version": "0.1.0",
                    "private": True,
                    "scripts": {"start": "node dist/index.js", "build": "tsc"},
                    "devDependencies": {"typescript": "^5.6.0"},
                },
                indent=2,
            )
            + "\n",
        },
        {
            "path": f"{name}/tsconfig.json",
            "content": json.dumps(
                {"compilerOptions": {"outDir": "dist", "strict": True, "target": "ES2020", "module": "commonjs"}, "include": ["src"]},
                indent=2,
            )
            + "\n",
        },
        {
            "path": f"{name}/src/index.ts",
            "content": f'''export class App {{
  constructor(private goal: string) {{}}
  run(): void {{
    if (!this.goal.trim()) throw new Error("goal required");
    console.log(`Running: ${{this.goal}}`);
  }}
}}

new App({goal!r}).run();
''',
        },
    ]


def _gen_html(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    return [
        {
            "path": f"{name}/index.html",
            "content": f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{name}</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header><h1>{name}</h1><p>{goal}</p></header>
  <main id="app"><p>Generated page. Edit freely.</p></main>
  <script src="app.js"></script>
</body>
</html>
''',
        },
        {
            "path": f"{name}/styles.css",
            "content": "body{font-family:system-ui;margin:2rem;background:#0b0e14;color:#e8ecf3}header{margin-bottom:1.5rem}h1{margin:0 0 .5rem}\n",
        },
        {
            "path": f"{name}/app.js",
            "content": "console.log('app ready');\ndocument.getElementById('app').insertAdjacentHTML('beforeend','<p>JS loaded.</p>');\n",
        },
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\nOpen `index.html` in a browser.\n\n{goal}\n",
        },
    ]


def _gen_csharp(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    proj = name.replace("-", "_")
    return [
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\n{goal}\n\n```bash\ndotnet run --project {proj}\n```\n",
        },
        {
            "path": f"{name}/{proj}/{proj}.csproj",
            "content": """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
""",
        },
        {
            "path": f"{name}/{proj}/Program.cs",
            "content": f'''using System;

var goal = "{goal[:80]}";
if (string.IsNullOrWhiteSpace(goal))
    throw new ArgumentException("goal required");

Console.WriteLine($"App: {{goal}}");
// WinForms/WPF can replace this console stub page-by-page.
''',
        },
    ]


def _gen_rust(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    return [
        {
            "path": f"{name}/Cargo.toml",
            "content": f'[package]\nname = "{name.replace("-", "_")}"\nversion = "0.1.0"\nedition = "2021"\n',
        },
        {
            "path": f"{name}/src/main.rs",
            "content": f'''fn main() {{
    let goal = "{goal[:80]}";
    if goal.is_empty() {{
        panic!("goal required");
    }}
    println!("goal: {{goal}}");
}}
''',
        },
        {"path": f"{name}/README.md", "content": f"# {name}\n\n```bash\ncargo run\n```\n\n{goal}\n"},
    ]


def _gen_go(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    return [
        {
            "path": f"{name}/go.mod",
            "content": f"module {name}\n\ngo 1.22\n",
        },
        {
            "path": f"{name}/main.go",
            "content": f'''package main

import (
    "fmt"
    "log"
)

func main() {{
    goal := "{goal[:80]}"
    if goal == "" {{
        log.fatal("goal required")
    }}
    fmt.Println("goal:", goal)
}}
''',
        },
        {"path": f"{name}/README.md", "content": f"# {name}\n\n```bash\ngo run .\n```\n\n{goal}\n"},
    ]


def _gen_java(name: str, prompt: str, goal: str) -> list[dict[str, str]]:
    pkg = name.replace("-", "")
    return [
        {
            "path": f"{name}/README.md",
            "content": f"# {name}\n\n{goal}\n\n```bash\njavac src/Main.java && java -cp src Main\n```\n",
        },
        {
            "path": f"{name}/src/Main.java",
            "content": f'''public class Main {{
    public static void main(String[] args) {{
        String goal = "{goal[:80]}";
        if (goal == null || goal.isBlank()) {{
            throw new IllegalArgumentException("goal required");
        }}
        System.out.println("goal: " + goal);
    }}
}}
''',
        },
    ]



async def generate_project_with_model(prompt: str, project_goal: str = "", router=None) -> dict[str, Any]:
    """Run the capability-routed task graph. Template generation remains the caller's fallback."""
    if router is None:
        raise ValueError("router is required for model generation")
    from generation.orchestrator import orchestrate_generation
    return await orchestrate_generation(prompt, project_goal, router)

def self_heal(
    error_text: str,
    files: list[dict[str, str]],
    language: str = "python",
) -> dict[str, Any]:
    """Propose fixed file versions given an error message."""
    start = time.perf_counter()
    err = (error_text or "").lower()
    patches: list[dict[str, str]] = []
    reasons: list[str] = []

    for f in files:
        path = f.get("path") or ""
        content = f.get("content") or ""
        new_content = content
        changed = False

        if "modulenotfounderror" in err or "cannot find module" in err:
            if path.endswith("requirements.txt") and "fastapi" in err:
                if "fastapi" not in content:
                    new_content = content + "fastapi>=0.115.0\n"
                    changed = True
                    reasons.append("Added missing dependency to requirements.txt")
        if "syntaxerror" in err or "expected" in err:
            if language == "python" and path.endswith(".py"):
                # ensure final newline
                if not content.endswith("\n"):
                    new_content = content + "\n"
                    changed = True
                    reasons.append(f"Normalized trailing newline in {path}")
        if "undefined reference" in err or "unresolved external" in err:
            if path.endswith(".cpp") or path.endswith(".c"):
                reasons.append(f"Link error – check {path} is listed in the build file")
        if "goal" in err and "empty" in err:
            reasons.append("Validation rejected empty goal – pass a non-empty project goal")

        if changed:
            patches.append({"path": path, "content": new_content, "action": "replace"})

    if not patches and not reasons:
        reasons.append(
            "No automatic patch pattern matched. Share the full error + language for a deeper fix, "
            "or open the failing file and request Suggest / Evolve."
        )
        # Provide a generic debug wrapper suggestion
        if language == "python":
            patches.append(
                {
                    "path": "debug_wrapper.py",
                    "content": (
                        "import traceback\n"
                        "try:\n"
                        "    import main\n"
                        "    main.main()\n"
                        "except Exception:\n"
                        "    traceback.print_exc()\n"
                    ),
                    "action": "create",
                }
            )
            reasons.append("Added debug_wrapper.py to capture full stack traces")

    return {
        "patches": patches,
        "reasons": reasons,
        "error_excerpt": error_text[:500],
        "latency_ms": int((time.perf_counter() - start) * 1000) + 20,
        "ok": bool(patches) or bool(reasons),
    }


def files_to_zip(files: list[dict[str, str]]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            path = f.get("path") or "file.txt"
            content = f.get("content") or ""
            z.writestr(path, content)
    return buf.getvalue()


FILE_BLOCK_RE = re.compile(r"===FILE:\s*(.+?)===\n(.*?)\n===END===", re.DOTALL)
GENERATOR_SYSTEM_PROMPT = """You are DreamCoder's implementation engineer, not a scaffolding tool.
When asked to build an app, implement the requested product completely enough to run and demonstrate the requested behavior.
Respond ONLY with a sequence of file blocks in this exact format:
===FILE: path/to/file.ext===
<complete file contents>
===END===

Rules:
- Translate EVERY concrete requirement in the user request into working code, UI, routes, state, data handling, and assets as applicable.
- Do not create placeholder stubs, fake features, coming-soon screens, TODO-only functions, or generic hello-world substitutes when the request asks for a real feature.
- Do not merely create a project structure: implement the behavior.
- Include every file required to run the app: manifests, configuration, entry points, templates/static assets, data setup, and tests when appropriate.
- Prefer a small dependency set and do not invent dependencies that are unnecessary for the requested stack.
- Include useful error handling and a runnable entry point.
- The generated app must demonstrate the requested core workflow immediately after installation/startup.
- For desktop/web UI, implement the actual controls, interactions, persistence/state, and visual layout described by the user rather than mock buttons.
- If the request names a reference product, reproduce the requested capabilities and interaction model without copying proprietary source code.
- Do not claim a feature is implemented unless its code is present in the returned files.
- No prose and no markdown fences outside file blocks.
"""

async def generate_project_with_model(prompt: str, project_goal: str, router) -> dict[str, Any]:
    """Run DreamCoder's multi-model planner -> implementer -> reviewer pipeline."""
    from generation.orchestrator import orchestrate_generation
    return await orchestrate_generation(prompt, project_goal, router)


async def generate_project_with_model(prompt: str, project_goal: str = "", router=None, model: str = "Local Model") -> dict[str, Any]:
    """Generate a project through the selected model, with a deterministic template fallback.

    The model is an orchestration input, not a policy bypass. If its response is
    unavailable or malformed, DreamCoder still returns a reviewable scaffold.
    """
    if router is None:
        from main import router as router
    from models.base import ChatContext

    request = (
        "Generate a benign software project from this request. Return JSON only with "
        "keys name, summary, files. files must be an array of objects with path and content. "
        "Keep the project self-contained and include tests when practical. Do not use "
        "markdown fences around the JSON.\n\n"
        f"Goal: {project_goal or prompt}\nRequest: {prompt}"
    )
    started = time.perf_counter()
    try:
        response = await router.chat(model, ChatContext(message=request, mode="analysis"))
        raw = response.content.strip()
        match = re.search(r"\\{.*\\}", raw, re.S)
        if match:
            payload = json.loads(match.group(0))
            files = payload.get("files")
            if isinstance(files, list) and files and all(isinstance(x, dict) and x.get("path") is not None and x.get("content") is not None for x in files):
                stack = _detect_stack(prompt)
                name = str(payload.get("name") or _slug(prompt))
                return {
                    "name": name,
                    "prompt": prompt,
                    "goal": project_goal or prompt.strip()[:200],
                    "stack": stack,
                    "files": [{"path": str(x["path"]), "content": str(x["content"])} for x in files],
                    "pages": [{"id":"model","title":"Model generation","detail":f"Generated by {model}"}],
                    "file_count": len(files),
                    "latency_ms": int((time.perf_counter()-started)*1000),
                    "summary": str(payload.get("summary") or f"Generated {len(files)}-file project"),
                    "run_hint": _run_hint(stack, name),
                    "self_heal_ready": True,
                    "source": "model",
                    "model": model,
                }
    except Exception:
        pass

    result = generate_project(prompt, project_goal)
    result["source"] = "template-fallback"
    result["model"] = model
    result["latency_ms"] = int((time.perf_counter()-started)*1000)
    return result
