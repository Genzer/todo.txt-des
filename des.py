#!/usr/bin/env python3

import argparse
import sys
import os
import re
from subprocess import call
from random import getrandbits
from hashlib import sha256
from fileinput import FileInput
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

DESCRIPTION_ID_PATTERN = re.compile(r'des:(?P<des_id>[a-zA-Z0-9]+)')

@dataclass
class Task:
    id: int
    original_content: str
    description_id: int = None


def parse_task(task_id: int, original_content: str) -> Task:
    """Returns a new `Task` from the id and the original content in todo.txt

    This function will look for the tag `des:XXXX` which contains the id of
    the description generated by this plugin.
    """
    match = DESCRIPTION_ID_PATTERN.search(original_content)
    if match and match.group('des_id'):
        description_id = match.group('des_id')
        return Task(
            id=task_id,
            original_content=original_content,
            description_id=description_id
        )
    return Task(id=task_id, original_content=original_content)

def get_task(task_id: int) -> Optional[Task]:
    """Reads the whole content of the task in todo.txt file
    """
    
    with todotxt() as todo_file:
        for i, line in enumerate(todo_file):
            line: str = line
            if i == task_id - 1:
                return parse_task(task_id, line)

    return None

@contextmanager
def todotxt(write: bool = False):
    todo_file = os.getenv('TODO_FILE')
    try:
        f = open(todo_file, 'w' if write else 'r')
        yield f
    finally:
        f.close()

def get_description_file(description_id: int) -> Path:
    description_dir: Path = Path(os.getenv('TODO_DIR')) / 'descriptions'

    if not description_dir.exists():
        description_dir.mkdir()

    if not description_dir.is_dir():
        raise ValueError(f"{description_dir} is not a directory")

    description_file: Path = description_dir / f"{description_id}.txt"

    return description_file

def get_description_content(description_id: int) -> str:
    description_file = get_description_file(description_id)

    if not description_file.is_file():
        raise ValueError(f"{description_file} is not a file")

    with open(description_file, 'r') as df:
        return "".join(df.readlines())

def edit_description(task_id: int) -> None:
    task = get_task(task_id)

    if task is None:
        raise ValueError(f"Task #{task_id} not found in todo.txt")

    if task.description_id:
        description_file = get_description_file(task.description_id)
        editor = os.getenv('EDITOR', os.getenv('TODO_DESCRIPTION_EDITOR', 'vi'))
        call([editor, description_file])
    else:
        raise ValueError(f"No description found for task {task_id}")


def add_description(task_id: int, description: str) -> None:
    task = get_task(task_id)
    
    if task is None:
        raise ValueError(f"Task #{task_id} not found in todo.txt")

    description_dir: Path = Path(os.getenv('TODO_DIR')) / 'descriptions'

    if not description_dir.is_dir():
            raise ValueError(f"{description_dir} is not a directory")

    # NOTE:
    # ----
    # Use SHA256 to hash the `task.original_content` and `task_id` to generate an id.
    # The hash in HEX is truncated to get the first 8 charaters. (like a Git commit)
    description_id = sha256(str(getrandbits(256)).encode('utf-8')).hexdigest()[:8]

    description_file: Path = description_dir / f"{description_id}.txt"
    
    with open(description_file, "w", encoding="utf-8") as df:
        df.write(description)

    with FileInput(os.getenv('TODO_FILE'), inplace=True, mode="rb", backup=".bak") as todo:
        for index, line in enumerate(todo, start=1):
            if index == task_id:
                trip_existing_description = re.sub(DESCRIPTION_ID_PATTERN.pattern, '', line.decode())
                print(f"{trip_existing_description.strip()} des:{description_id}", end='\n')
            else:
                print(line.decode(), end='')

def show_description(task_id: int) -> None:
    """Prints the description associcating with the `task_id`
    """
    task = get_task(task_id)

    if task is None:
        raise ValueError(f"Task #{task_id} not found in todo.txt")

    if task.description_id:
        description_full = get_description_content(task.description_id)
        print(description_full)
    else:
        raise ValueError(f"No description found for task {task_id}")

def optionally_from_stdin(input):
    """Parse the command line arguments to check whether to read the `description`
    value as is or takes from /dev/stdin (data are piped in)
    """
    if input == "-":
        return "".join(sys.stdin.readlines()).strip()
    if isinstance(input, str):
        return input
    return str(input)


def main(arguments: list):
    parser = argparse.ArgumentParser(prog="todo-des")
    sub_parsers = parser.add_subparsers()

    add_des_parser = sub_parsers.add_parser(
        name="add",
        aliases=['a'],
        help="Add description into task")

    add_des_parser.add_argument(
        "task_id",
        help="todo.txt task id",
        type=int)

    add_des_parser.add_argument(
        "description",
        help="""
        Description of the task. Use - if you want to read from stdin
        """,
        type=optionally_from_stdin)

    show_des_parser = sub_parsers.add_parser(
        name="show",
        aliases="s",
        help="Show description task")

    show_des_parser.add_argument(
        "task_id",
        help="todo.txt task id",
        type=int)

    edit_des_parser = sub_parsers.add_parser(
        name="edit",
        aliases=['e'],
        help="Edit the description of the task"
    )

    edit_des_parser.add_argument(
        "task_id",
        help="todo.txt task id",
        type=int)

    show_des_parser.set_defaults(func=show_description)
    add_des_parser.set_defaults(func=add_description)
    edit_des_parser.set_defaults(func=edit_description)

    parsed_args: dict = parser.parse_args(arguments)
    input = dict(vars(parsed_args))
    del input['func']
    parsed_args.func(**input)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except ValueError as e:
        print(e)
        sys.exit(1)