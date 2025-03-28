import { AppBar, Toolbar, Typography, Button, Box } from '@mui/material';
import { Link } from 'react-router-dom';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" sx={{ backgroundColor: 'white', boxShadow: 'none' }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1, color: 'black' }}>
            <Link to="/OpenRCA/" style={{ textDecoration: 'none', color: 'inherit' }}>
              OpenRCA
            </Link>
          </Typography>
          {/* <Button color="inherit" component={Link} to="/about" sx={{ color: 'black' }}>
            About
          </Button> */}
          <Button color="inherit" component={Link} to="https://iclr.cc/virtual/2025/poster/32093" sx={{ color: 'black' }}>
            Paper
          </Button>
          <Button color="inherit" component={Link} to="https://github.com/microsoft/OpenRCA" sx={{ color: 'black' }}>
            Code
          </Button>
        </Toolbar>
      </AppBar>
      <Box component="main">
        {children}
      </Box>
    </Box>
  );
};

export default Layout; 