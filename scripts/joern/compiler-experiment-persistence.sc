import io.shiftleft.semanticcpg.language.*

@main def compilerExperimentPersistence(cpgFile: String): Unit = {
  importCpg(cpgFile)

  println("MNCS_FORGE_COMPILER_EXPERIMENT_PERSISTENCE")
  val targets = List(
    "record",
    "list",
    "compare",
    "_get",
    "new_record",
    "_validate_fields",
    "commit",
    "compiler_experiment_record",
    "compiler_experiments_list",
    "compiler_experiments_compare",
    "invoke"
  )
  targets.foreach { name =>
    val methods = cpg.method.nameExact(name).filter(_.filename.endsWith(".py")).l
    val files = methods.map(_.filename).distinct.sorted.mkString(",")
    val callers = methods.flatMap(_.callIn.method.name.l).distinct.sorted.mkString(",")
    val callees = methods.flatMap(_.callOut.name.l).distinct.sorted.mkString(",")
    val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|$name|count=${methods.size}|files=$files|callers=$callers|callees=$callees|controls=$controls")
  }

  cpg.call
    .filter(_.file.name.headOption.exists(path =>
      path.endsWith("compiler_studies.py") || path.endsWith("compiler_evolution.py") ||
      path.endsWith("operations.py") || path.endsWith("engine.py") || path.endsWith("records.py")
    ))
    .filter(call => call.name.matches(
      "from_language_record|compare_compiler_experiments|new_record|commit|records|parse_record|candidate_disposition|candidate_freeze|final_evaluation_run|verifier_.*"
    ))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" + call.method.name + ":" + call.name + ":" + call.lineNumber.getOrElse(-1))
    .l.sorted.foreach(value => println(s"PERSISTENCE_BOUNDARY|$value"))
}
