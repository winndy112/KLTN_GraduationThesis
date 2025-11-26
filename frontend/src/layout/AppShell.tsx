import { AppShell, Burger, Group, NavLink, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconHome, IconCpu, IconWorld, IconGavel, IconAlertTriangle, IconListSearch } from '@tabler/icons-react';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';

export function MainLayout() {
    const [opened, { toggle }] = useDisclosure();
    const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true);
    const navigate = useNavigate();
    const location = useLocation();

    const links = [
        { icon: IconHome, label: 'Home', to: '/' },
        { icon: IconCpu, label: 'Sensors', to: '/sensors' },
        { icon: IconWorld, label: 'CTI Integration', to: '/cti' },
        { icon: IconGavel, label: 'Rules Engine', to: '/rules' },
        { icon: IconAlertTriangle, label: 'Alerts', to: '/alerts' },
        { icon: IconListSearch, label: 'Logs', to: '/logs' },
    ];

    const items = links.map((link) => (
        <NavLink
            key={link.label}
            label={link.label}
            leftSection={<link.icon size="1rem" stroke={1.5} />}
            active={location.pathname === link.to}
            onClick={() => {
                navigate(link.to);
                if (window.innerWidth < 768) {
                    toggle();
                }
            }}
        />
    ));

    return (
        <AppShell
            header={{ height: 60 }}
            navbar={{
                width: 300,
                breakpoint: 'sm',
                collapsed: { mobile: !opened, desktop: !desktopOpened },
            }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md">
                    <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
                    <Burger opened={desktopOpened} onClick={toggleDesktop} visibleFrom="sm" size="sm" />
                    <Title order={3}>Security Dashboard</Title>
                </Group>
            </AppShell.Header>

            <AppShell.Navbar p="md">
                {items}
            </AppShell.Navbar>

            <AppShell.Main>
                <Outlet />
            </AppShell.Main>
        </AppShell>
    );
}
