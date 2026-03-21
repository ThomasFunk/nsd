PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share/nsd
DESTDIR ?=

PYTHON ?= python3

INSTALL ?= install
RM ?= rm -rf

.PHONY: all install uninstall reinstall

all:
	@echo "Nothing to build. Use: make install"

install:
	$(INSTALL) -d "$(DESTDIR)$(DATADIR)"
	$(INSTALL) -d "$(DESTDIR)$(BINDIR)"
	$(INSTALL) -m 755 nsd.py "$(DESTDIR)$(DATADIR)/nsd.py"
	$(INSTALL) -m 644 nsd.conf "$(DESTDIR)$(DATADIR)/nsd.conf"
	cp -r locale "$(DESTDIR)$(DATADIR)/"
	cp -r protocols "$(DESTDIR)$(DATADIR)/"
	printf '%s\n' '#!/usr/bin/env sh' \
		'exec "$(PYTHON)" "$(DATADIR)/nsd.py" "$$@"' \
		> "$(DESTDIR)$(BINDIR)/nsd"
	chmod 755 "$(DESTDIR)$(BINDIR)/nsd"

uninstall:
	$(RM) "$(DESTDIR)$(BINDIR)/nsd"
	$(RM) "$(DESTDIR)$(DATADIR)"

reinstall: uninstall install
