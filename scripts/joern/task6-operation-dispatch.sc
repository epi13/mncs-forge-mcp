import io.shiftleft.semanticcpg.language.*

@main def task6OperationDispatch(cpgFile: String): Unit = {
  importCpg(cpgFile)

  println("TASK6_JOERN_OPERATION_DISPATCH")
  List("cli.py", "server.py", "operations.py").foreach { suffix =>
    val calls = cpg.call
      .filter(_.file.name.headOption.exists(_.endsWith(suffix)))
      .filter(call => call.name.matches(
        "doctor|project_inspect|state_inspect|claim_.*|provider_.*|capability_blockers|" +
        "verifier_.*|epoch_begin|candidate_.*|development_checks_run|failure_explain|" +
        "final_evaluation_run|evidence_reconcile|bundle_build|invoke"
      ))
      .map(call => call.file.name.headOption.getOrElse("?") + ":" +
        call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
      .l.sorted
    println(s"FILE|$suffix|MATCHED_CALL_COUNT|${calls.size}")
    calls.foreach(value => println(s"CALL|$suffix|$value"))
  }

  val modeChecks = cpg.call.name("_require_mode|_require_development|invoke")
    .filter(_.file.name.headOption.exists(name => List(
      "cli.py", "server.py", "operations.py", "providers.py", "state_machine.py"
    ).exists(name.endsWith)))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
    .l.sorted
  modeChecks.foreach(value => println(s"MODE_OR_INVOKE|$value"))
}
