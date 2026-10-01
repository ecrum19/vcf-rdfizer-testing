# Lets a direct `latexmk current.tex` (VS Code LaTeX Workshop, or a terminal)
# find what the Makefile otherwise copies into .build/current/: the Springer
# class in template/, its bibliography style in template/bst/, and the figures
# in figures/ (the ZIP) or ../paper-assets/ (the repository).
# The trailing // makes kpathsea search subdirectories.
ensure_path('TEXINPUTS', './template//', './figures//', '../paper-assets//');
ensure_path('BSTINPUTS', './template/bst//');

# LaTeX Workshop can start latexmk without the TeX Live binaries on PATH.
$ENV{'PATH'} = '/Library/TeX/texbin:' . $ENV{'PATH'} if -d '/Library/TeX/texbin';
$pdf_mode = 1;
