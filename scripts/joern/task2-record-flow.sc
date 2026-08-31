import io.shiftleft.semanticcpg.language.*

@main def task2RecordFlow(cpgFile: String): Unit = {
  importCpg(cpgFile)
  val watchedCalls = Set(
    "_read_unlocked", "_read_unlocked_raw", "_verify_records", "_verify_raw_records",
    "append", "derive_record_identity", "local_json_identity", "new_record", "normalize",
    "normalize_ledger_entry", "terminal_unknown_result", "to_json", "to_object_dict",
    "_write_immutable"
  )
  val targets = List(
    "_write_immutable", "append", "records", "_read_unlocked", "_read_unlocked_raw",
    "epoch_begin", "candidate_register", "provider_probe", "development_checks_run",
    "_execution_record", "candidate_disposition", "candidate_freeze",
    "final_evaluation_run", "evidence_reconcile", "bundle_build", "run", "_execute",
    "new_record", "normalize", "normalize_ledger_entry", "derive_record_identity"
  )
  println("TASK2_JOERN_RECORD_FLOW")
  targets.foreach { name =>
    val methods = cpg.method.nameExact(name).filter(_.filename.endsWith(".py")).l
    val files = methods.map(_.filename).distinct.sorted.mkString(",")
    val callers = methods.flatMap(_.callIn.method.name.l).distinct.sorted.mkString(",")
    val callees = methods.flatMap(_.callOut.name.l).filter(watchedCalls).distinct.sorted.mkString(",")
    val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|$name|count=${methods.size}|files=$files|callers=$callers|callees=$callees|controls=$controls")
  }
  println("IMMUTABLE_CALLS")
  cpg.call.nameExact("_write_immutable")
    .map(c => c.file.name.headOption.getOrElse("?") + ":" + c.lineNumber.getOrElse(-1) + ":" + c.code)
    .l.sorted.foreach(println)
}
