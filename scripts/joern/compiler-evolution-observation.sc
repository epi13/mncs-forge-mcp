import io.shiftleft.semanticcpg.language.*

@main def compilerEvolutionObservation(cpgFile: String): Unit = {
  importCpg(cpgFile)

  println("MNCS_FORGE_COMPILER_EVOLUTION_OBSERVATION")
  val targets = List(
    "new_record",
    "parse_record",
    "execute",
    "run",
    "from_language_record",
    "compare_compiler_experiments"
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
      path.endsWith("compiler_evolution.py") || path.endsWith("workflows.py") || path.endsWith("records.py")
    ))
    .filter(call => call.name.matches("new_record|parse_record|json_object|validate|from_language_record|compare_compiler_experiments"))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" + call.method.name + ":" + call.name + ":" + call.lineNumber.getOrElse(-1))
    .l.sorted.foreach(value => println(s"BOUNDARY_CALL|$value"))
}
