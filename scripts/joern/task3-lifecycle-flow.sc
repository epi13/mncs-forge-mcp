import io.shiftleft.semanticcpg.language.*

@main def task3LifecycleFlow(cpgFile: String): Unit = {
  importCpg(cpgFile)
  val targets = List(
    "epoch_begin", "candidate_register", "development_checks_run", "candidate_compare",
    "candidate_disposition", "candidate_freeze", "final_evaluation_run",
    "evidence_reconcile", "bundle_build", "run", "_execute",
    "authorize_epoch_begin", "authorize_candidate_register", "authorize_candidate_disposition",
    "authorize_candidate_freeze", "authorize_evaluator_entry", "authorize_terminal_result",
    "inspect"
  )
  val watchedCalls = Set(
    "_require_mode", "_records", "_latest_payload", "_record_by_id", "_candidate",
    "_verify_freeze", "authorize_epoch_begin", "authorize_candidate_register",
    "authorize_candidate_disposition", "authorize_candidate_freeze",
    "authorize_evaluator_entry", "authorize_terminal_result", "inspect",
    "terminal_unknown_result", "_write_immutable", "append"
  )
  println("TASK3_JOERN_LIFECYCLE_FLOW")
  targets.foreach { name =>
    val methods = cpg.method.nameExact(name).filter(_.filename.endsWith(".py")).l
    val files = methods.map(_.filename).distinct.sorted.mkString(",")
    val callers = methods.flatMap(_.callIn.method.name.l).distinct.sorted.mkString(",")
    val callees = methods.flatMap(_.callOut.name.l).filter(watchedCalls).distinct.sorted.mkString(",")
    val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|$name|count=${methods.size}|files=$files|callers=$callers|callees=$callees|controls=$controls")
  }
  println("MODE_GUARD_CALLS")
  cpg.call.nameExact("_require_mode")
    .map(c => c.file.name.headOption.getOrElse("?") + ":" + c.lineNumber.getOrElse(-1) + ":" + c.code)
    .l.sorted.foreach(println)
  println("LIFECYCLE_RECORD_READS")
  cpg.call.nameExact("_records", "_latest_payload", "_record_by_id", "_candidate", "_verify_freeze")
    .map(c => c.file.name.headOption.getOrElse("?") + ":" + c.lineNumber.getOrElse(-1) + ":" + c.method.name + ":" + c.code)
    .l.sorted.foreach(println)
  println("TRANSITION_CALLS")
  cpg.call.name("authorize_.*")
    .map(c => c.file.name.headOption.getOrElse("?") + ":" + c.lineNumber.getOrElse(-1) + ":" + c.method.name + ":" + c.name)
    .l.sorted.foreach(println)
}
