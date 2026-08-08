import io.shiftleft.semanticcpg.language.*

@main def task5ServiceBoundaries(cpgFile: String): Unit = {
  importCpg(cpgFile)

  val sourceMethods = cpg.method.filter(_.filename.endsWith(".py"))
  val engineNamedMethods = sourceMethods.filter(_.filename.endsWith("engine.py"))
    .filter(_.lineNumber.isDefined)
    .filterNot(method => method.name.contains("<") || method.name.contains("lambda"))
    .name.l.distinct.sorted

  println("TASK5_JOERN_SERVICE_BOUNDARIES")
  println(s"ENGINE_NAMED_METHOD_COUNT|${engineNamedMethods.size}")
  engineNamedMethods.foreach(name => println(s"ENGINE_NAMED_METHOD|$name"))

  val watchedCalls = List(
    "run_bounded", "LocalRecordStore", "commit", "recover",
    "ForgeStateMachine", "authorize_.*"
  )
  watchedCalls.foreach { pattern =>
    cpg.call.name(pattern)
    .filter(_.file.name.headOption.exists(_.contains("mncs_forge/")))
      .map(call => call.file.name.headOption.getOrElse("?") + ":" +
        call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
      .l.sorted.foreach(value => println(s"CALL|$pattern|$value"))
  }

  println("ENGINE_CALLERS")
  sourceMethods.filter(_.filename.endsWith("engine.py")).foreach { method =>
    val callers = method.callIn.method
      .filter(_.filename.endsWith(".py"))
      .map(caller => caller.filename + ":" + caller.name)
      .l.distinct.sorted
    if (callers.nonEmpty) {
      println(s"ENGINE_METHOD|${method.name}|callers=${callers.mkString(",")}")
    }
  }

  println("APPLICATION_CALLS")
  cpg.call
    .filter(_.file.name.headOption.exists(_.contains("/application/")))
    .map(call => call.file.name.headOption.getOrElse("?") + ":" +
      call.lineNumber.getOrElse(-1) + ":" + call.method.name + ":" + call.name)
    .l.sorted.foreach(println)
}
