export interface Data {
  name: string;
  model: string;
  org: string;
  correct: string;
  partial: string;
  date: string;
}

// 模型颜色映射
export const modelColorMap: { [key: string]: { color: string, backgroundColor: string } } = {
  'Claude 3.5 Sonnet': { color: '#1a237e', backgroundColor: '#e8eaf6' },
  'GPT-4o': { color: '#004d40', backgroundColor: '#e0f2f1' },
  'Gemini 1.5 Pro': { color: '#b71c1c', backgroundColor: '#ffebee' },
  'Mistral Large 2': { color: '#0d47a1', backgroundColor: '#bbdefb' },
  'Command R+': { color: '#4a148c', backgroundColor: '#e1bee7' },
  'Llama 3.1 Instruct': { color: '#e65100', backgroundColor: '#ffe0b2' }
};

// 组织图标映射
export const orgLogoMap: { [key: string]: string } = {
  'Microsoft': '/OpenRCA/ms_logo.svg',
  'Google': '/OpenRCA/google_logo.svg',
  'OpenAI': '/OpenRCA/openai_logo.svg',
  'Anthropic': '/OpenRCA/anthropic_logo.svg',
  'Meta': '/OpenRCA/meta_logo.svg'
};

// 新闻数据
export const news = [
  { date: '2025/1/23', content: 'Our paper has been accepted by ICLR 2025.' },
  { date: '2025/1/23', content: 'Released OpenRCA dataset with 335 failure cases.' }
];

// 模型数据
export const modelData: Data[] = [
  // Closed Models - RCA-Agent
  { name: 'RCA-Agent', model: 'Claude 3.5 Sonnet', org: 'Microsoft', correct: '11.34%', partial: '17.31%', date: '2025/1/23' },
  { name: 'RCA-Agent', model: 'GPT-4o', org: 'Microsoft', correct: '8.96%', partial: '17.91%', date: '2025/1/23' },
  { name: 'RCA-Agent', model: 'Gemini 1.5 Pro', org: 'Microsoft', correct: '2.69%', partial: '6.87%', date: '2025/1/23' },
  
  // Closed Models - Balanced
  { name: 'Prompting (Balanced)', model: 'Claude 3.5 Sonnet', org: 'Microsoft', correct: '3.88%', partial: '18.81%', date: '2025/1/23' },
  { name: 'Prompting (Balanced)', model: 'GPT-4o', org: 'Microsoft', correct: '3.28%', partial: '14.33%', date: '2025/1/23' },
  { name: 'Prompting (Balanced)', model: 'Gemini 1.5 Pro', org: 'Microsoft', correct: '6.27%', partial: '24.18%', date: '2025/1/23' },
  
  // Closed Models - Oracle
  { name: 'Prompting (Oracle)', model: 'Claude 3.5 Sonnet', org: 'Microsoft', correct: '5.37%', partial: '17.61%', date: '2025/1/23' },
  { name: 'Prompting (Oracle)', model: 'GPT-4o', org: 'Microsoft', correct: '6.27%', partial: '15.82%', date: '2025/1/23' },
  { name: 'Prompting (Oracle)', model: 'Gemini 1.5 Pro', org: 'Microsoft', correct: '7.16%', partial: '23.58%', date: '2025/1/23' },
  
  // Open Source Models - Balanced
  { name: 'Prompting (Balanced)', model: 'Mistral Large 2', org: 'Microsoft', correct: '3.58%', partial: '6.40%', date: '2025/1/23' },
  { name: 'Prompting (Balanced)', model: 'Command R+', org: 'Microsoft', correct: '4.18%', partial: '8.96%', date: '2025/1/23' },
  { name: 'Prompting (Balanced)', model: 'Llama 3.1 Instruct', org: 'Microsoft', correct: '2.99%', partial: '14.63%', date: '2025/1/23' },
  
  // Open Source Models - Oracle
  { name: 'Prompting (Oracle)', model: 'Mistral Large 2', org: 'Microsoft', correct: '4.48%', partial: '10.45%', date: '2025/1/23' },
  { name: 'Prompting (Oracle)', model: 'Command R+', org: 'Microsoft', correct: '4.78%', partial: '7.46%', date: '2025/1/23' },
  { name: 'Prompting (Oracle)', model: 'Llama 3.1 Instruct', org: 'Microsoft', correct: '3.88%', partial: '14.93%', date: '2025/1/23' },
  
  // Open Source Models - RCA-Agent
  { name: 'RCA-Agent', model: 'Llama 3.1 Instruct', org: 'Microsoft', correct: '3.28%', partial: '5.67%', date: '2025/1/23' }
]; 