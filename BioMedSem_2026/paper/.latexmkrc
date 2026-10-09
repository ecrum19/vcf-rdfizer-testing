# Lets a direct `latexmk current_short.tex` (VS Code LaTeX Workshop, or a terminal)
# find what the Makefile otherwise copies into .build/current_short/: the Springer
# class in template/, its bibliography style in template/bst/, and the figures
# in figures/ (the ZIP) or ../paper-assets/ (the repository).
# The trailing // makes kpathsea search subdirectories.
ensure_path('TEXINPUTS', './template//', './figures//', '../paper-assets//');
ensure_path('BSTINPUTS', './template/bst//');

# LaTeX Workshop can start latexmk without the TeX Live binaries on PATH.
$ENV{'PATH'} = '/Library/TeX/texbin:' . $ENV{'PATH'} if -d '/Library/TeX/texbin';
$pdf_mode = 1;

# Each document reads the other's labels from its .aux (xr-hyper). The Makefile
# builds both in .build/; a direct build of one of them here (LaTeX Workshop, or
# `latexmk current_short.tex`) would find no partner .aux and print ?? for every
# cross-document reference. So it first builds the partner when the partner's .aux
# is missing or older than its source. The environment variable stops the partner
# build from starting another one.
unless ($ENV{VCFR_XR_PARTNER}) {
  my %partner = ('current_short' => 'supplementary', 'supplementary' => 'current_short');
  for my $arg (@ARGV) {
    (my $base = $arg) =~ s{^.*/}{};
    $base =~ s/\.tex$//;
    my $other = $partner{$base} or next;
    next unless -e "$other.tex";
    if (!-e "$other.aux" || (stat("$other.tex"))[9] > (stat("$other.aux"))[9]) {
      local $ENV{VCFR_XR_PARTNER} = 1;
      system('latexmk', '-pdf', '-interaction=nonstopmode', '-file-line-error', "$other.tex");
    }
  }
}
