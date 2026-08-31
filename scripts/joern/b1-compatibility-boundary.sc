import io.shiftleft.semanticcpg.language.*

@main def b1CompatibilityBoundary(cpgFile: String): Unit = {
  importCpg(cpgFile)

  println("B1_COMPATIBILITY_BOUNDARY")
  List("_legacy", "normalize", "parse_record", "new_record", "load_config", "commit", "invoke")
    .foreach { name =>
      val methods = cpg.method.nameExact(name).filter(_.filename.endsWith(".py")).l
      val files = methods.map(_.filename).distinct.sorted.mkString(",")
      val callers = methods.flatMap(_.callIn.method.name.l).distinct.sorted.mkString(",")
      val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
        .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
      println(s"METHOD|$name|count=${methods.size}|files=$files|callers=$callers|controls=$controls")
    }

  println("LEGACY_NORMALIZATION_CALLS")
  cpg.call.nameExact("_legacy")
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name)
    .l.sorted.foreach(println)

  println("CURRENT_RECORD_CONSTRUCTION_CALLS")
  cpg.call.nameExact("new_record")
    .filter(_.file.name.headOption.exists(_.endsWith(".py")))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name)
    .l.sorted.foreach(println)

  println("APPLICATION_COMMIT_CALLS")
  cpg.call.nameExact("commit")
    .filter(_.file.name.headOption.exists(name =>
      name.contains("/application/") || name.endsWith("micro_verifiers.py")))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name)
    .l.sorted.foreach(println)
}
