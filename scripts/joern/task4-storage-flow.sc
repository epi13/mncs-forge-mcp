import io.shiftleft.semanticcpg.language.*

@main def task4StorageFlow(cpgFile: String): Unit = {
  importCpg(cpgFile)
  val targets = List(
    "_record_provider_probe", "epoch_begin", "candidate_register", "development_checks_run",
    "candidate_disposition", "candidate_freeze", "final_evaluation_run", "bundle_build",
    "run", "_write_immutable", "append", "commit", "recover",
    "_recover_stranded_verifier_actions"
  )
  val watched = Set(
    "_write_immutable", "append", "commit", "recover", "_recover_stranded_verifier_actions",
    "terminal_unknown_result", "recovered_terminal_unknown_result", "authorize_terminal_result"
  )
  println("TASK4_JOERN_STORAGE_FLOW")
  targets.foreach { name =>
    val methods = cpg.method.nameExact(name).filter(_.filename.endsWith(".py")).l
    val files = methods.map(_.filename).distinct.sorted.mkString(",")
    val callers = methods.flatMap(_.callIn.method.name.l).distinct.sorted.mkString(",")
    val callees = methods.flatMap(_.callOut.name.l).filter(watched).distinct.sorted.mkString(",")
    val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|$name|count=${methods.size}|files=$files|callers=$callers|callees=$callees|controls=$controls")
  }
  println("APPLICATION_STORAGE_CALLS")
  cpg.call.nameExact("_write_immutable", "append", "commit")
    .filter(call => call.file.name.headOption.exists(name =>
      name.endsWith("engine.py") || name.endsWith("micro_verifiers.py")))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
    .l.sorted.foreach(println)
  println("RECOVERY_TERMINAL_CALLS")
  cpg.call.name(".*terminal.*unknown.*|authorize_terminal_result.*")
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
    .l.sorted.foreach(println)
}
