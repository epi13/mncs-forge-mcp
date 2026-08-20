import io.shiftleft.semanticcpg.language.*

@main def windowsLauncherTest(cpgFile: String): Unit = {
  importCpg(cpgFile)
  println("MNCS_FORGE_WINDOWS_LAUNCHER_TEST")
  val methods = cpg.method.nameExact("test_codex_launcher_uses_relocatable_module_entrypoint")
    .filter(_.filename.endsWith("test_cli_mcp_edgestream.py")).l
  methods.foreach { method =>
    val calls = method.callOut.name.l.distinct.sorted.mkString(",")
    val controls = method.controlStructure.controlStructureType.l
      .groupBy(identity).view.mapValues(_.size).toMap.toSeq.sortBy(_._1).mkString(",")
    println(s"METHOD|${method.name}|file=${method.filename}|calls=$calls|controls=$controls")
  }
}
