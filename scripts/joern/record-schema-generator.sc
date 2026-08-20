import io.shiftleft.semanticcpg.language.*

@main def recordSchemaGenerator(cpgFile: String): Unit = {
  importCpg(cpgFile)
  println("MNCS_FORGE_RECORD_SCHEMA_GENERATOR")
  List("property_schema", "record_schema", "main").foreach { name =>
    val methods = cpg.method.nameExact(name)
      .filter(_.file.name.headOption.exists(_.endsWith("generate-record-schema.py"))).l
    val callees = methods.flatMap(_.callOut.name.l).distinct.sorted.mkString(",")
    val controls = methods.flatMap(_.controlStructure.controlStructureType.l)
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|$name|count=${methods.size}|callees=$callees|controls=$controls")
  }
}
