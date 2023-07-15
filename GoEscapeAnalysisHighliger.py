import sublime
import sublime_plugin
import subprocess
import re
import os
import threading

# This plugin performs escape analysis on Go code and highlights the
# lines where heap allocations are made. This is useful for optimizing
# Go code to reduce heap allocations.


class GoEscapeAnalysisHighlighterCommand(sublime_plugin.TextCommand):

    instance = None  # singleton
    enabled = False  # whether the escape analysis is enabled

    def __init__(self, view):
        super().__init__(view)
        GoEscapeAnalysisHighlighterCommand.instance = self

    # called to run the command.
    def run(self, edit):

        # Toggle the enabled state.
        GoEscapeAnalysisHighlighterCommand.enabled = not GoEscapeAnalysisHighlighterCommand.enabled

        if GoEscapeAnalysisHighlighterCommand.enabled:
            self.escape_analysis(self.view)
        else:
            self.erase_regions(self.view)

    # Clear the highlights.
    def erase_regions(self, view):
        view.erase_regions('go_heap_allocations')

    # Perform the escape analysis.
    def escape_analysis(self, view):
        # Save the current file before performing the analysis.
        view.run_command('save')

        filename = view.file_name()
        directory_name = os.path.dirname(filename)

        # Run the Go build command to perform the escape analysis.
        result = subprocess.run(
            ["go", "build", "-gcflags", "-m"],
            capture_output=True,
            text=True,
            cwd=directory_name)

        # Parse the output.
        pattern = re.compile(r'(.*.go):(\d+):\d+:\s(.*?) escapes to heap')
        matches = pattern.findall(result.stderr)

        # Clear previous highlights.
        self.erase_regions(view)

        # Iterate over the matches and highlight the respective lines.
        regions = []
        for match in matches:

            file_name = match[0]
            line_number = match[1]
            content = match[2]

            # Check if this escape analysis result is for the current file.
            if view.file_name() == os.path.abspath(
                    os.path.join(directory_name, file_name)):

                point = view.text_point(int(line_number) - 1, 0)
                line_region = view.line(point)
                regions.append(line_region)

        view.add_regions('go_heap_allocations', regions,
                         'invalid',
                         'dot',
                         sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE)


# This plugin listens to events and performs the escape analysis
# whenever a file is modified or the user switches to a different
# file.
class GoEscapeAnalysisListener(sublime_plugin.EventListener):

    def __init__(self):
        super().__init__()
        self.timer = None

    # Debounce the analysis so that it is only performed after the user
    # has stopped typing.
    def debounce_analyze(self, view):
        # Cancel the previous timer.
        if self.timer is not None:
            self.timer.cancel()

        # Create a new timer.
        self.timer = threading.Timer(
            2.5,
            GoEscapeAnalysisHighlighterCommand.instance.escape_analysis,
            args=[view])
        self.timer.start()

    # Called when a view gains input focus
    def on_activated(self, view):
        if GoEscapeAnalysisHighlighterCommand.instance is None:
            return

        if GoEscapeAnalysisHighlighterCommand.enabled:
            self.debounce_analyze(view)
        else:
            GoEscapeAnalysisHighlighterCommand.instance.erase_regions(view)

    # Called when a view is modified
    def on_modified(self, view):
        if GoEscapeAnalysisHighlighterCommand.instance is None:
            return

        if GoEscapeAnalysisHighlighterCommand.enabled:
            self.debounce_analyze(view)
