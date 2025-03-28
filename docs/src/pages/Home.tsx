import { Box, Typography, Container, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TableSortLabel, Button, IconButton, Snackbar, Chip, Menu, MenuItem, Checkbox, ListItemText } from '@mui/material';
import { useState } from 'react';
import EmailIcon from '@mui/icons-material/Email';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import DescriptionIcon from '@mui/icons-material/Description';
import GitHubIcon from '@mui/icons-material/GitHub';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import FilterListIcon from '@mui/icons-material/FilterList';
import { Data, modelColorMap, orgLogoMap, news, modelData } from '../data/modelData';

type Order = 'asc' | 'desc';

const prefix = '/OpenRCA'

// 比较函数
function getComparator(order: Order, orderBy: keyof Data) {
  return (a: Data, b: Data) => {
    // 处理百分比字符串和日期
    const getValue = (value: string) => {
      if (value.endsWith('%')) {
        return parseFloat(value.slice(0, -1)); // 移除%并转换为数字
      }
      if (orderBy === 'date') {
        return new Date(value).getTime();
      }
      return value;
    };

    const valueA = getValue(a[orderBy]);
    const valueB = getValue(b[orderBy]);

    // 数字比较（包括百分比和日期）
    if (typeof valueA === 'number' && typeof valueB === 'number') {
      return order === 'desc' ? valueB - valueA : valueA - valueB;
    }

    // 字符串比较
    return order === 'desc' 
      ? String(valueB).localeCompare(String(valueA))
      : String(valueA).localeCompare(String(valueB));
  };
}

const Home = () => {
  const [order, setOrder] = useState<Order>('desc');
  const [orderBy, setOrderBy] = useState<keyof Data>('correct');
  const [openSnackbarCite, setOpenSnackbarCite] = useState(false);
  const [openSnackbarMail, setOpenSnackbarMail] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>(Object.keys(modelColorMap));
  const [modelFilterAnchor, setModelFilterAnchor] = useState<null | HTMLElement>(null);

  const handleRequestSort = (property: keyof Data) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const handleModelFilterClick = (event: React.MouseEvent<HTMLElement>) => {
    setModelFilterAnchor(event.currentTarget);
  };

  const handleModelFilterClose = () => {
    setModelFilterAnchor(null);
  };

  const handleModelToggle = (model: string) => {
    setSelectedModels(prev => {
      if (prev.includes(model)) {
        return prev.filter(m => m !== model);
      } else {
        return [...prev, model];
      }
    });
  };

  const handleSelectAllModels = () => {
    if (selectedModels.length === Object.keys(modelColorMap).length) {
      setSelectedModels([]);
    } else {
      setSelectedModels(Object.keys(modelColorMap));
    }
  };

  // 过滤数据
  const filteredAndSortedData = [...modelData]
    .filter(row => selectedModels.includes(row.model))
    .sort(getComparator(order, orderBy));

  // 找出最高值
  const maxCorrect = Math.max(...filteredAndSortedData.map(row => parseFloat(row.correct)));
  const maxPartial = Math.max(...filteredAndSortedData.map(row => parseFloat(row.partial)));

  const headCells: Array<{
    id: keyof Data;
    label: string | JSX.Element;
    width: string;
    sortable: boolean;
  }> = [
    { id: 'name', label: 'Method Name', width: '25%', sortable: false },
    { 
      id: 'model', 
      label: (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
          Model
          <IconButton 
            size="small" 
            onClick={handleModelFilterClick}
            sx={{ 
              color: 'inherit',
              padding: '2px',
              '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.1)' }
            }}
          >
            <FilterListIcon fontSize="small" />
          </IconButton>
          <Menu
            anchorEl={modelFilterAnchor}
            open={Boolean(modelFilterAnchor)}
            onClose={handleModelFilterClose}
            PaperProps={{
              sx: {
                maxHeight: 300,
                width: 200,
                backgroundColor: '#ffffff'
              }
            }}
          >
            <MenuItem onClick={handleSelectAllModels}>
              <Checkbox 
                checked={selectedModels.length === Object.keys(modelColorMap).length}
                indeterminate={selectedModels.length > 0 && selectedModels.length < Object.keys(modelColorMap).length}
              />
              <ListItemText primary="Select All" />
            </MenuItem>
            {Object.keys(modelColorMap).map((model) => (
              <MenuItem key={model} onClick={() => handleModelToggle(model)}>
                <Checkbox checked={selectedModels.includes(model)} />
                <ListItemText 
                  primary={
                    <Chip 
                      label={model}
                      size="small"
                      sx={{
                        color: modelColorMap[model].color,
                        backgroundColor: modelColorMap[model].backgroundColor,
                        fontWeight: 500,
                        border: `1px solid ${modelColorMap[model].color}`
                      }}
                    />
                  }
                />
              </MenuItem>
            ))}
          </Menu>
        </Box>
      ),
      width: '20%',
      sortable: false 
    },
    { id: 'org', label: 'Org.', width: '15%', sortable: false },
    { id: 'correct', label: 'Correct', width: '15%', sortable: true },
    { id: 'partial', label: 'Partial', width: '15%', sortable: true },
    { id: 'date', label: 'Date', width: '10%', sortable: true },
  ];

  const handleCopyClick = () => {
    const citationText = `@inproceedings{
xu2025openrca,
title={Open{RCA}: Can Large Language Models Locate the Root Cause of Software Failures?},
author={Junjielong Xu and Qinan Zhang and Zhiqing Zhong and Shilin He and Chaoyun Zhang and Qingwei Lin and Dan Pei and Pinjia He and Dongmei Zhang and Qi Zhang},
booktitle={The Thirteenth International Conference on Learning Representations},
year={2025},
url={https://openreview.net/forum?id=M4qNIzQYpd}
}`;
    navigator.clipboard.writeText(citationText);
    setOpenSnackbarCite(true);
  };

  return (
    <Box sx={{ 
      background: '#ffffff',
      minHeight: '100vh',
      pt: 4
    }}>
      <Container maxWidth="lg" sx={{ maxWidth: '1080px !important' }}>
        <Box sx={{ my: 4 }}>
          <Typography 
            variant="h4" 
            component="h1" 
            gutterBottom
            sx={{
              background: 'linear-gradient(45deg, #2196F3 30%, #1565C0 90%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              fontWeight: 600,
              mb: 3,
              textAlign: 'center'
            }}
          >
            OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?
          </Typography>
          <Typography 
            variant="subtitle1" 
            sx={{ 
              mb: 4,
              color: '#424242',
              lineHeight: 1.8,
              textAlign: 'center'
            }}
          >
            OpenRCA includes 335 failures from three enterprise software systems, along with over 68 GB of telemetry data (logs, metrics, and traces). Given a failure case and its associated telemetry, the LLM is tasked to identify the root cause of the failure, requiring comprehension of software dependencies and reasoning over heterogeneous, long-context telemetry data.
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            gap: 2,
            mt: -1,
            mb: 1 ,
            ml: 2,
            zIndex: -1
          }}>
            <Box
              component="img"
              src={`${prefix}/microsoft.jpg`}
              alt="Microsoft Logo"
              onClick={() => window.open('https://www.microsoft.com', '_blank')}
              sx={{
                height: 100,
                objectFit: 'contain',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'scale(1.05)'
                }
              }}
            />
            <Box
              component="img" 
              src={`${prefix}/cuhksz.png`}
              alt="CUHK-SZ Logo"
              onClick={() => window.open('https://www.cuhk.edu.cn/', '_blank')}
              sx={{
                height: 30,
                objectFit: 'contain',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'scale(1.05)'
                },
                zIndex: 1000
              }}
            />
            <Box
              component="img"
              src={`${prefix}/thu.jpg`}
              alt="Tsinghua Logo"
              onClick={() => window.open('https://www.tsinghua.edu.cn', '_blank')}
              sx={{
                height: 70,
                objectFit: 'contain',
                cursor: 'pointer',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'scale(1.05)'
                },
                marginLeft: '-1vw'
              }}
            />
          </Box>
          </Typography>

          <Box sx={{ mt: 6 }}>
            <Typography 
              variant="h5" 
              gutterBottom
              sx={{
                background: 'linear-gradient(45deg, #2196F3 30%, #1565C0 90%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontWeight: 600,
                mb: 3,
                textAlign: 'center'
              }}
            >
              News
            </Typography>
            <Paper sx={{ 
              p: 3, 
              backgroundColor: '#ffffff',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)',
              '& .MuiTypography-paragraph': {
                color: '#424242',
                position: 'relative',
                pl: 3,
                mb: 2,
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: '4px',
                  height: '4px',
                  borderRadius: '50%',
                  background: 'linear-gradient(45deg, #2196F3 30%, #1565C0 90%)'
                }
              }
            }}>
              {news.map((news, index) => (
                <Typography key={index} variant="body1" paragraph>
                  {news.date} {news.content}
                </Typography>
              ))}
            </Paper>
          </Box>

          <Box sx={{ 
            mt: 6,
            backgroundColor: '#f8fafc',
            borderRadius: '12px',
            p: 3,
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)'
          }}>
            <Typography 
              variant="h5" 
              sx={{ 
                mb: 2, 
                background: 'linear-gradient(45deg, #2196F3 30%, #1565C0 90%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontWeight: 600,
                textAlign: 'center'
              }}
            >
              Leaderboard
            </Typography>
            
            <TableContainer 
              component={Paper} 
              sx={{ 
                boxShadow: 'none',
                backgroundColor: 'transparent',
                maxHeight: 400,
                overflow: 'overlay',
                '&::-webkit-scrollbar': {
                  width: '6px',
                  height: '6px',
                  backgroundColor: 'transparent'
                },
                '&::-webkit-scrollbar-track': {
                  background: 'transparent',
                  borderRadius: '3px'
                },
                '&::-webkit-scrollbar-thumb': {
                  background: 'rgba(33, 150, 243, 0.6)',
                  borderRadius: '3px',
                  '&:hover': {
                    background: 'rgba(21, 101, 192, 0.8)'
                  }
                },
                '@media (hover: hover)': {
                  '&::-webkit-scrollbar-thumb': {
                    visibility: 'hidden'
                  },
                  '&:hover::-webkit-scrollbar-thumb': {
                    visibility: 'visible'
                  }
                }
              }}
            >
              <Table 
                stickyHeader 
                size="small"
                sx={{
                  '& .MuiTableCell-root': {
                    padding: '8px 16px',
                  }
                }}
              >
                <TableHead>
                  <TableRow>
                    {headCells.map((headCell) => (
                      <TableCell 
                        key={headCell.id}
                        sortDirection={orderBy === headCell.id ? order : false}
                        sx={{ 
                          width: headCell.width,
                          backgroundColor: '#1976d2',
                          color: 'white',
                          fontWeight: 600,
                          textAlign: 'center'
                        }}
                      >
                        {typeof headCell.label === 'string' ? (
                          headCell.sortable ? (
                            <TableSortLabel
                              active={orderBy === headCell.id}
                              direction={orderBy === headCell.id ? order : 'asc'}
                              onClick={() => handleRequestSort(headCell.id)}
                              sx={{
                                width: '100%',
                                justifyContent: 'center',
                                '&.MuiTableSortLabel-root': {
                                  color: 'white',
                                },
                                '&.MuiTableSortLabel-root:hover': {
                                  color: 'white',
                                },
                                '&.Mui-active': {
                                  color: 'white',
                                },
                                '& .MuiTableSortLabel-icon': {
                                  color: 'white !important',
                                },
                              }}
                            >
                              {headCell.label}
                            </TableSortLabel>
                          ) : (
                            headCell.label
                          )
                        ) : (
                          headCell.label
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredAndSortedData.map((row, index) => (
                    <TableRow 
                      key={row.name + row.model}
                      sx={{ 
                        '&:last-child td, &:last-child th': { border: 0 },
                        backgroundColor: row.model.includes('*') ? 'rgba(0, 0, 0, 0.02)' : 'inherit'
                      }}
                    >
                      <TableCell sx={{ width: '25%', textAlign: 'center', fontWeight: 600 }}>
                        {row.name}
                      </TableCell>
                      <TableCell sx={{ width: '20%', textAlign: 'center' }}>
                        <Chip 
                          label={row.model}
                          size="small"
                          sx={{
                            color: modelColorMap[row.model.replace('*', '')]?.color || '#000',
                            backgroundColor: modelColorMap[row.model.replace('*', '')]?.backgroundColor || '#f5f5f5',
                            fontWeight: 500,
                            '&:hover': {
                              backgroundColor: modelColorMap[row.model.replace('*', '')]?.backgroundColor || '#f5f5f5',
                            }
                          }}
                        />
                      </TableCell>
                      <TableCell sx={{ width: '15%', textAlign: 'center' }}>
                        <Box
                          component="img"
                          src={orgLogoMap[row.org] || `${prefix}/default_logo.svg`}
                          alt={`${row.org} Logo`}
                          sx={{
                            height: 20,
                            width: 'auto',
                            objectFit: 'contain',
                            opacity: row.model.includes('*') ? 0.7 : 1,
                            filter: row.model.includes('*') ? 'grayscale(20%)' : 'none'
                          }}
                        />
                      </TableCell>
                      <TableCell 
                        sx={{ 
                          width: '15%', 
                          textAlign: 'center',
                          fontWeight: parseFloat(row.correct) === maxCorrect ? 600 : 'inherit',
                          color: parseFloat(row.correct) === maxCorrect ? '#1976d2' : 'inherit'
                        }}
                      >
                        {row.correct}
                      </TableCell>
                      <TableCell 
                        sx={{ 
                          width: '15%', 
                          textAlign: 'center',
                          fontWeight: parseFloat(row.partial) === maxPartial ? 600 : 'inherit',
                          color: parseFloat(row.partial) === maxPartial ? '#1976d2' : 'inherit'
                        }}
                      >
                        {row.partial}
                      </TableCell>
                      <TableCell sx={{ width: '10%', textAlign: 'center' }}>{row.date}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>

          <Box sx={{ 
            mt: 4, 
            p: 3,
            backgroundColor: '#E65100',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            color: 'white',
            boxShadow: '0 4px 20px rgba(230, 81, 0, 0.2)'
          }}>
            <Typography variant="h6" sx={{ fontWeight: 500 }}>
              Is your model or agent up to the challenge? Submit your results here!
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                startIcon={<EmailIcon />}
                onClick={() => {
                  navigator.clipboard.writeText('openrcanon@gmail.com');
                  setOpenSnackbarMail(true);
                }}
                sx={{
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  }
                }}
              >
                Contact
              </Button>
              <Snackbar
                open={openSnackbarMail}
                autoHideDuration={3000}
                onClose={() => setOpenSnackbarMail(false)}
                message="Mail has been copied to clipboard!"
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
              />
              <Button
                variant="contained"
                startIcon={<FileUploadIcon />}
                component="a"
                href="mailto:openrcanon@gmail.com"
                sx={{
                  backgroundColor: '#000000',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                  }
                }}
              >
                Submit
              </Button>
            </Box>
          </Box>

          {/* 提交须知 */}
          <Paper sx={{ 
            mt: 2, 
            p: 3, 
            backgroundColor: '#fff8e1', 
            borderRadius: '12px',
            border: '1px solid #ffecb3',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)'
          }}>
            <Typography 
              variant="subtitle1" 
              sx={{ 
                fontWeight: 600, 
                color: '#E65100',
                mb: 1.5
              }}
            >
              Submission Guidelines
            </Typography>
            <Typography variant="body2" sx={{ color: '#424242', mb: 1.5, lineHeight: 1.6 }}>
            If you want to have your results included, please include the following in your email:
            </Typography>
            <Box sx={{ 
              display: 'flex', 
              flexDirection: 'column',
              gap: 1,
              pl: 2,
              '& .MuiTypography-root': {
                position: 'relative',
                pl: 2.5,
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: '0.5em',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#E65100'
                }
              }
            }}>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                Name of your method
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                Inference results in valid format (see <a href="https://github.com/microsoft/OpenRCA?tab=readme-ov-file#%EF%B8%8F-evaluation" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2', textDecoration: 'underline' }}>GitHub repository</a>)
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                Accuracy of your method tested in your own environment
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                (Optional) Link to your repository
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                (Optional) Execution trajectory of your method
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                (Optional) Reproduction guidelines of your method
              </Typography>
              <Typography variant="body2" sx={{ color: '#424242' }}>
                (Optional) Docker image of your method and environment
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ color: '#666', mt: 1.5, fontStyle: 'italic' }}>
              Note: Inclusion in the leaderboard will be attempted on a best-effort basis. We cannot guarantee the timely processing of requests.
            </Typography>
          </Paper>

          <Box sx={{ mt: 6 }}>
            <Typography 
              variant="h5" 
              sx={{
                color: '#2c3e50',
                fontWeight: 600,
                mb: 3,
                textAlign: 'left'
              }}
            >
              What is the task in OpenRCA?
            </Typography>
            <Typography 
              variant="h6" 
              sx={{ 
                color: '#2c3e50',
                fontWeight: 500,
                mb: 2,
                textAlign: 'left'
              }}
            >
              Identify the root cause of the failure!
            </Typography>
            {/* 加上图片 */}
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 4 }}>
              <img src={`${prefix}/overview.png`} alt="OpenRCA Task" style={{ maxWidth: '100%', height: 'auto' }} />
            </Box>
            <Typography 
              variant="body1" 
              sx={{ 
                color: '#424242',
                mb: 4,
                lineHeight: 1.8,
                textAlign: 'left'
              }}
            >
              Each OpenRCA task is based on a real-world failure case from a software system and its associated telemetry data. Given the failure case and its associated telemetry, the task is to identify the root cause of the failure, requiring comprehension of software dependencies and reasoning over heterogeneous, long-context telemetry data.
            </Typography>

          

            <Typography 
              variant="h5" 
              sx={{
                color: '#2c3e50',
                fontWeight: 600,
                mb: 3,
                mt: 6,
                textAlign: 'left',
                marginTop: '15vh'
              }}
            >
              Check out our paper for more details!
            </Typography>
            
            <Typography 
              variant="h6" 
              sx={{ 
                color: '#2c3e50',
                fontWeight: 500,
                mb: 2,
                textAlign: 'center'
              }}
            >
              OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?
            </Typography>

            <Box sx={{ mb: 3, textAlign: 'center' }}>
              <Typography variant="body1" sx={{ color: '#424242' }}>
              Junjielong Xu<sup>1,2</sup>, Qinan Zhang<sup>1</sup>, Zhiqing Zhong<sup>1</sup>, Shilin He<sup>2</sup>, Chaoyun Zhang<sup>2</sup>, Qingwei Lin<sup>2</sup>, Dan Pei<sup>3</sup>, Pinjia He<sup>1</sup>, Dongmei Zhang<sup>2</sup>, Qi Zhang<sup>2</sup>
              </Typography>
              <Typography variant="body2" sx={{ color: '#666', mt: 1 }}>
                <sup>1</sup>School of Data Science, The Chinese University of Hong Kong, Shenzhen <sup>2</sup>Microsoft <sup>3</sup>Tsinghua University
                <br></br>
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, mb: 4, justifyContent: 'center' }}>
              <Button
                variant="contained"
                startIcon={<DescriptionIcon />}
                href="https://iclr.cc/virtual/2025/poster/32093"
                sx={{
                  backgroundColor: '#1565C0',
                  '&:hover': {
                    backgroundColor: '#1976D2',
                  }
                }}
              >
                Paper
              </Button>
              <Button
                variant="contained"
                startIcon={<GitHubIcon />}
                href="https://github.com/microsoft/OpenRCA"
                sx={{
                  backgroundColor: '#2c3e50',
                  '&:hover': {
                    backgroundColor: '#34495e',
                  }
                }}
              >
                Code
              </Button>
            </Box>

            <Typography 
              variant="body2" 
              sx={{ 
                color: '#666',
                mb: 2,
                textAlign: 'center'
              }}
            >
              If you have any remaining questions, please feel free to contact us at <a href="mailto:openrcanon@gmail.com">openrcanon@gmail.com</a>
            </Typography>

            <Typography 
              variant="h5" 
              sx={{
                color: '#2c3e50',
                fontWeight: 600,
                mb: 3,
                mt: 6
              }}
            >
              Citing this work
            </Typography>
            <Typography 
              variant="body1" 
              sx={{ 
                color: '#424242',
                mb: 2
              }}
            >
              If you use this benchmark, please cite:
            </Typography>
            <Paper 
              sx={{ 
                p: 3,
                backgroundColor: '#fdf6e3',
                borderRadius: '8px',
                position: 'relative',
                '& pre': {
                  margin: 0,
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  lineHeight: 1.8,
                  color: '#2c3e50',
                  whiteSpace: 'pre-wrap'
                },
                '& .bibtex': {
                  color: '#a0522d'
                },
                '& .identifier': {
                  color: '#8b4513'
                },
                '& .field': {
                  color: '#0086b3'
                },
                '& .value': {
                  color: '#22863a'
                }
              }}
            >
              <IconButton
                onClick={handleCopyClick}
                sx={{
                  position: 'absolute',
                  right: 8,
                  top: 8,
                  backgroundColor: 'rgba(0, 0, 0, 0.03)',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 0, 0, 0.08)'
                  }
                }}
              >
                <ContentCopyIcon />
              </IconButton>
              <pre>
<span className="bibtex">@inproceedings</span>&#123;<span className="identifier">xu2025openrca</span>,
<br></br>
<span>     </span>
  <span className="field">title</span>=&#123;<span className="value">OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?</span>&#125;,
  <br></br>
  <span>     </span>
  <span className="field">author</span>=&#123;<span className="value">Junjielong Xu and Qinan Zhang and Zhiqing Zhong and Shilin He and Chaoyun Zhang and Qingwei Lin and</span>
  <br></br>
  <span>             </span>
  <span className="value">Dan Pei and Pinjia He and Dongmei Zhang and Qi Zhang</span>&#125;,
  <br></br>
  <span>     </span>
  <span className="field">booktitle</span>=&#123;<span className="value">The Thirteenth International Conference on Learning Representations</span>&#125;,
  <br></br>
  <span>     </span>
  <span className="field">year</span>=&#123;<span className="value">2025</span>&#125;,
  <br></br>
  <span>     </span>
  <span className="field">url</span>=&#123;<span className="value">https://openreview.net/forum?id=M4qNIzQYpd</span>&#125;
  <br></br>
&#125;</pre>
            </Paper>
            <Snackbar
              open={openSnackbarCite}
              autoHideDuration={2000}
              onClose={() => setOpenSnackbarCite(false)}
              message="Citation copied to clipboard"
              anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            />
          </Box>
        </Box>
      </Container>
    </Box>
  );
};

export default Home; 