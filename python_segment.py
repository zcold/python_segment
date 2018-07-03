import sublime
import sublime_plugin
import types


IDLE = 'state_idle'
CODE = 'state_code'

class PythonSegmentCommand(sublime_plugin.TextCommand):

    def is_enabled(self):
        syntax = self.view.settings().get('syntax').lower()
        settings = sublime.load_settings('python_segment.sublime-settings')
        supported_file_types = settings.get('comment', {'Python': '#'}).items()
        self.comment = None
        for s, c in supported_file_types:
            if s.lower() not in syntax:
                continue
            self.comment = c
            break
        if self.comment is None:
            return False

        self.fast_line_start = settings.get('fast_line_start', 'py_fast')
        self.segment_start = settings.get('segment_start', 'pycode')
        self.segment_end = settings.get('segment_end', 'pyend')
        self.only_in_comment = settings.get('only_in_comment', True)
        self.segment_done = settings.get('segment_done', 'pydone')
        return True

    def run_py(self, code):
        result = []
        try:
            exec(code)
            self.good = True
        except Exception as e:
            result = ['{}: {}'.format(i+1, line) for i, line in enumerate(code.split('\n'))]
            result += ['--------']
            result += str(e).split('\n')
            self.good = False
        return result

    def format_code(self):
        for segment in self.pysource:
            first_line = segment.code[0]
            offset = len(first_line) - len(first_line[len(self.comment):].lstrip())
            segment.code = '\n'.join(map(lambda s: s[offset:], segment.code))
            if segment.type == 'fast_line':
                extra_offset = len(self.fast_line_start)
            elif segment.type == 'python_segment':
                extra_offset = len(self.segment_start)
            else:
                extra_offset = 0
            segment.offset = offset+extra_offset+segment.col

    def get_code(self):
        def get_comment(line):
            if self.comment in line:
                index = line.index(self.comment)
                return line[index:].lstrip(), index
            return None, 0

        view_content = self.view.substr(sublime.Region(0, self.view.size()))
        self.pysource = []
        state = IDLE
        current_segment = types.SimpleNamespace()
        for line_no, line in enumerate(view_content.split('\n')):
            comment_text, col = get_comment(line)
            if not comment_text:
                if self.only_in_comment:
                    state = IDLE
                if not hasattr(current_segment, 'end_line'):
                    current_segment.end_line = line_no
                continue

            if state == IDLE and not hasattr(current_segment, 'end_line'):
                current_segment.end_line = line_no

            if state == CODE:
                current_segment.code += [comment_text]

            if self.fast_line_start in comment_text and self.segment_done not in comment_text:
                index = comment_text.index(self.fast_line_start)
                comment_text = comment_text[index+len(self.fast_line_start):]
                to_assign, i_range = comment_text.split('when')
                to_assign, i_range = to_assign.strip(), i_range.strip()
                i, i_range = i_range.split('in')
                i, i_range = i.strip(), i_range.strip()
                i_range = '# for {} in {}:'.format(i, i_range)
                to_assign = '#     result += [\'{}\'.format({}={})]'.format(to_assign, i, i)
                segment = types.SimpleNamespace()
                segment.start_line = line_no
                segment.end_line = line_no+1
                segment.code = [i_range, to_assign]
                segment.col = col
                segment.type = 'fast_line'
                self.pysource.append(segment)

            if self.segment_start in comment_text and self.segment_done not in comment_text:
                state = CODE
                segment = types.SimpleNamespace()
                segment.start_line = line_no
                segment.code = []
                segment.col = col
                segment.type = 'python_segment'
                self.pysource.append(segment)
                current_segment = self.pysource[-1]

            if self.segment_end in comment_text:
                state = IDLE

    def run(self, edit):
        self.get_code()
        self.format_code()
        previous_result_row = 0
        for segment in self.pysource:
            row = segment.end_line + previous_result_row
            result = self.run_py(segment.code)
            previous_result_row += len(result)
            result = ('\n' + ' '*segment.col).join(result) + '\n'
            self.view.insert(edit, self.view.text_point(row, 0), result)
            if self.good:
                r, c = segment.start_line, segment.offset
                text = ' '+self.segment_done
                self.view.insert(edit, self.view.text_point(r, c), text)
        # py_code py_this_is_done
        # for i in range(4):
        #   result += ['assign count_{i}'.format(**locals())]
