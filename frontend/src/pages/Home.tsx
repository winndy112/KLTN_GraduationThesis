import { Title, Text, Container, SimpleGrid, Card, ThemeIcon, Button } from '@mantine/core';
import { IconCpu, IconWorld, IconGavel, IconAlertTriangle, IconArrowRight } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

export default function Home() {
    const navigate = useNavigate();

    const modules = [
        {
            title: 'Sensors',
            description: 'Monitor agent status, heartbeats, and performance metrics.',
            icon: IconCpu,
            color: 'blue',
            to: '/sensors',
        },
        {
            title: 'CTI Integration',
            description: 'View MISP events, IOCs, and threat intelligence stats.',
            icon: IconWorld,
            color: 'green',
            to: '/cti',
        },
        {
            title: 'Rules Engine',
            description: 'Manage rule sets, convert IOCs, and deploy rules.',
            icon: IconGavel,
            color: 'orange',
            to: '/rules',
        },
        {
            title: 'Alerts',
            description: 'Real-time intrusion detection alerts and analysis.',
            icon: IconAlertTriangle,
            color: 'red',
            to: '/alerts',
        },
    ];

    return (
        <Container size="lg" py="xl">
            <Title order={1} ta="center" mb="xl">Security Dashboard</Title>
            <Text ta="center" c="dimmed" mb={50} size="lg">
                Centralized management for sensors, threat intelligence, rules, and alerts.
            </Text>

            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xl">
                {modules.map((feature) => (
                    <Card key={feature.title} shadow="md" radius="md" padding="xl" withBorder>
                        <ThemeIcon
                            size={50}
                            radius={50}
                            variant="light"
                            color={feature.color}
                            mb="md"
                        >
                            <feature.icon size={30} stroke={1.5} />
                        </ThemeIcon>

                        <Text fz="lg" fw={500} mt="md">
                            {feature.title}
                        </Text>
                        <Text c="dimmed" mt="sm" mb="md">
                            {feature.description}
                        </Text>

                        <Button
                            variant="light"
                            color={feature.color}
                            fullWidth
                            rightSection={<IconArrowRight size="1rem" />}
                            onClick={() => navigate(feature.to)}
                        >
                            Go to {feature.title}
                        </Button>
                    </Card>
                ))}
            </SimpleGrid>
        </Container>
    );
}
