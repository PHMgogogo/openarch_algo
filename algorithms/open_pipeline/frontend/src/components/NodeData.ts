export class NodeData {
  [key: string]: any
  node_type: string = ""
  title?: string | null = null
  next: string[] = []
  prev: string[] = []
  x: number = 0
  y: number = 0
  order: number = -1
  read_data: string[] = []
  write_data: string[] = []
  read_state: string[] = []
  write_state: string[] = []
  parameters: Record<string, any> = {}
  category: string = ""
}
