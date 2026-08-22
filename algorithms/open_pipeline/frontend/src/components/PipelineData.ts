import type { NodeData } from "./NodeData"

export class PipelineData {
    [key: string]: any
    name: string = ""
    id: string = ""
    nodes: Record<string, NodeData | undefined> = {}
}