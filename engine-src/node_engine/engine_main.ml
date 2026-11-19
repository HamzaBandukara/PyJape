(* PyJape engine entry point: the Jape engine reading GUI-protocol commands on
   stdin and writing its replies to stdout, talking to the Python front-end
   over a pipe. (The directory is called node_engine for historical reasons;
   it builds a native executable.) *)
let () = Dialogue.start ()
