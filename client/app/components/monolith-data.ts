export const projects = [
  {
    id: "monolith-core-api",
    type: "microservices",
    status: "Active",
    createdDate: "Oct 12, 2023",
    icon: "terminal",
  },
  {
    id: "customer-vault-db",
    type: "storage",
    status: "Paused",
    createdDate: "Sep 28, 2023",
    icon: "database",
  },
  {
    id: "edge-delivery-network",
    type: "cdn",
    status: "Active",
    createdDate: "Nov 04, 2023",
    icon: "language",
  },
  {
    id: "ai-inference-worker",
    type: "compute",
    status: "Active",
    createdDate: "Dec 01, 2023",
    icon: "memory",
  },
];

export const currentConfig = [
  { label: "Deployment Mode", value: "Rolling Update" },
  { label: "Build Image", value: "Alpine-Node-20" },
  { label: "Health Check", value: "Active" },
];
