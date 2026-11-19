(* 
    Copyright (C) 2003-19 Richard Bornat & Bernard Sufrin
     
        richard@bornat.me.uk
        sufrin@comlab.ox.ac.uk

    This file is part of the jape proof engine, which is part of jape.

    Jape is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    Jape is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with jape; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
    (or look at http://www.gnu.org).

*)

(* Modified for PyJape (2026): a Unix-free version of the original moresys.ml.

   The original used Unix.pipe / create_process_env / open_process / kill to
   run external "oracle" provers as child processes. PyJape builds the engine
   without the Unix library, so that feature is stubbed out: signal handling
   is a no-op, and trying to launch an external oracle raises an error.
   Nothing else in the engine depends on Unix.
*)

exception Interrupt (* in case you need it *)

type process_id =
|       Unixoid         of int
|       Windowsoid      of (in_channel*out_channel)

let ignorePipeSignals () = ()

(* run g; no interrupt handler is installed in this build *)
let onInterrupt _f g = ignore (g ())

let execute_in_env _cmd _args _env =
  failwith "external oracles are not available in this build of Jape"

let execute cmd args =
  execute_in_env cmd args []

let reap = function
| Unixoid    _   -> ()
| Windowsoid _   -> ()
