"""G-code core.

  words       — Word / Line, the text-formatting representation
  formatter   — render Line -> text (format_line is the dict adapter)
  dialects    — machine-family startup/shutdown adapters
  header      — build the opening block (object path + dict adapter)
  body        — build the motion/etch body
  footer      — build the closing block
  generator   — orchestrates header/body/footer into a whole program
  parser      — text -> ParsedLine, and -> Move/ArcMove/GCodeProgram
  validator/  — modular advisory validation (structure, dialect, safety)
"""
