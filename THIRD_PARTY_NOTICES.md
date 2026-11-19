# Third-party notices

PyJape's own code and the Jape proof engine are free software under the GNU
General Public License, version 2 or (at your option) any later version. See
[LICENSE](LICENSE).

The downloadable PyJape apps also contain the following software, each under
its own licence. All of these licences are compatible with the GPL.

| Component | What it does in PyJape | Licence |
|---|---|---|
| Jape proof engine and example logics, © 2003-19 Richard Bornat & Bernard Sufrin | the proof engine (`jape-engine`) and the logics in `examples/` | GPL v2 or later ([LICENSE](LICENSE)) |
| Python runtime and standard library, © Python Software Foundation | runs the PyJape app | PSF License v2. The full text, with notices for libraries bundled with Python, is copied from the Python used for the build into `licenses/python/LICENSE.txt` in the app |
| Tcl/Tk 8.6 | the GUI toolkit, via Python's tkinter | Tcl/Tk licence (BSD-style), [below](#tcltk) |
| OCaml 4.14 runtime and standard library, © INRIA | compiled into `jape-engine` | LGPL 2.1 with the OCaml linking exception, [below](#ocaml) |
| PyInstaller bootloader | starts the packaged app | GPL 2.0 with the bootloader exception, which allows it in any program ([PyInstaller licence](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)) |

On Linux, PyInstaller may also bundle shared libraries from the build system
that Tk uses (X11 and font libraries, for example). Each is under its own
permissive licence, which you can get from that project or from the
distribution's package copyright files.

## Tcl/Tk

```
This software is copyrighted by the Regents of the University of
California, Sun Microsystems, Inc., Scriptics Corporation, ActiveState
Corporation, Apple Inc. and other parties.  The following terms apply to
all files associated with the software unless explicitly disclaimed in
individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7013 (b) (3) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

## OCaml

The OCaml runtime and standard library are linked into the Jape engine
unmodified. The full LGPL 2.1 text is at
<https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html>.

```
In the following, "the OCaml Core System" refers to all files marked
"Copyright INRIA" in this distribution.

The OCaml Core System is distributed under the terms of the
GNU Lesser General Public License (LGPL) version 2.1 (included below).

As a special exception to the GNU Lesser General Public License, you
may link, statically or dynamically, a "work that uses the OCaml Core
System" with a publicly distributed version of the OCaml Core System
to produce an executable file containing portions of the OCaml Core
System, and distribute that executable file under terms of your
choice, without any of the additional requirements listed in clause 6
of the GNU Lesser General Public License.  By "a publicly distributed
version of the OCaml Core System", we mean either the unmodified OCaml
Core System as distributed by INRIA, or a modified version of the
OCaml Core System that is distributed under the conditions defined in
clause 2 of the GNU Lesser General Public License.  This exception
does not however invalidate any other reasons why the executable file
might be covered by the GNU Lesser General Public License.
```
