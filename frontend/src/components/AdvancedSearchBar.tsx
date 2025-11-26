import { TextInput, Group, Text, Modal, Table, Code, Title, Stack, Button } from '@mantine/core';
import { IconSearch, IconInfoCircle } from '@tabler/icons-react';
import { useDisclosure } from '@mantine/hooks';

interface AdvancedSearchBarProps {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
}

export default function AdvancedSearchBar({ value, onChange, placeholder }: AdvancedSearchBarProps) {
    const [opened, { open, close }] = useDisclosure(false);

    return (
        <>
            <Modal opened={opened} onClose={close} title={<Title order={4}>Search Guide</Title>} size="lg">
                <Stack gap="md">
                    <Text size="sm">
                        Use the search bar to filter alerts using specific fields and operators.
                        Combine multiple filters with spaces (implicit AND).
                    </Text>

                    <Table striped withTableBorder withColumnBorders>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Operator</Table.Th>
                                <Table.Th>Description</Table.Th>
                                <Table.Th>Example</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            <Table.Tr>
                                <Table.Td><Code>=</Code></Table.Td>
                                <Table.Td>Exact match</Table.Td>
                                <Table.Td><Code>rule_id=12345</Code></Table.Td>
                            </Table.Tr>
                            <Table.Tr>
                                <Table.Td><Code>!=</Code></Table.Td>
                                <Table.Td>Not equal</Table.Td>
                                <Table.Td><Code>sensor_id!=sensor-1</Code></Table.Td>
                            </Table.Tr>
                            <Table.Tr>
                                <Table.Td><Code>&gt;</Code></Table.Td>
                                <Table.Td>Greater than</Table.Td>
                                <Table.Td><Code>priority&gt;2</Code></Table.Td>
                            </Table.Tr>
                            <Table.Tr>
                                <Table.Td><Code>&lt;</Code></Table.Td>
                                <Table.Td>Less than</Table.Td>
                                <Table.Td><Code>priority&lt;5</Code></Table.Td>
                            </Table.Tr>
                            <Table.Tr>
                                <Table.Td><Code>contains</Code></Table.Td>
                                <Table.Td>Substring match</Table.Td>
                                <Table.Td><Code>msg contains malware</Code></Table.Td>
                            </Table.Tr>
                        </Table.Tbody>
                    </Table>

                    <div>
                        <Text fw={600} size="sm" mb="xs">Searchable Fields:</Text>
                        <Group gap="xs">
                            {['rule_id', 'priority', 'msg', 'src.ip', 'src.port', 'dst.ip', 'dst.port', 'sensor_id', 'action'].map(field => (
                                <Code key={field}>{field}</Code>
                            ))}
                        </Group>
                    </div>

                    <Text size="sm" c="dimmed">
                        Example: <Code>priority&lt;3 action=block msg contains exploit</Code>
                    </Text>
                </Stack>
            </Modal>

            <Group gap="xs" align="flex-end" style={{ flexGrow: 1 }}>
                <TextInput
                    placeholder={placeholder || "Advanced search: field=value, field>value, field contains text..."}
                    leftSection={<IconSearch size="1rem" />}
                    value={value}
                    onChange={(e) => onChange(e.currentTarget.value)}
                    style={{ flexGrow: 1 }}
                />
                <Button
                    variant="light"
                    leftSection={<IconInfoCircle size="1rem" />}
                    onClick={open}
                >
                    Search Guide
                </Button>
            </Group>
        </>
    );
}
