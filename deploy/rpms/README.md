# Docker RPM Packages for RHEL 9 (Offline Installation)

These RPM files are required to install Docker on a clean RHEL 9 machine
with no internet connection. Download these files on a machine WITH internet
and place them in this folder before transferring to the target VM.

## Exact Files Required

Download all files from the URLs below on your development machine:

### 1. containerd.io
- **Filename:** `containerd.io-1.6.31-3.1.el9.x86_64.rpm`
- **URL:** https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/containerd.io-1.6.31-3.1.el9.x86_64.rpm

### 2. docker-ce
- **Filename:** `docker-ce-26.1.4-1.el9.x86_64.rpm`
- **URL:** https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-ce-26.1.4-1.el9.x86_64.rpm

### 3. docker-ce-cli
- **Filename:** `docker-ce-cli-26.1.4-1.el9.x86_64.rpm`
- **URL:** https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-ce-cli-26.1.4-1.el9.x86_64.rpm

### 4. docker-buildx-plugin
- **Filename:** `docker-buildx-plugin-0.14.1-1.el9.x86_64.rpm`
- **URL:** https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-buildx-plugin-0.14.1-1.el9.x86_64.rpm

### 5. docker-compose-plugin
- **Filename:** `docker-compose-plugin-2.27.1-1.el9.x86_64.rpm`
- **URL:** https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-compose-plugin-2.27.1-1.el9.x86_64.rpm

## How to Download (on your development machine)

### On Windows (PowerShell):
```powershell
cd deploy\rpms

Invoke-WebRequest -Uri "https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/containerd.io-1.6.31-3.1.el9.x86_64.rpm" -OutFile "containerd.io-1.6.31-3.1.el9.x86_64.rpm"

Invoke-WebRequest -Uri "https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-ce-26.1.4-1.el9.x86_64.rpm" -OutFile "docker-ce-26.1.4-1.el9.x86_64.rpm"

Invoke-WebRequest -Uri "https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-ce-cli-26.1.4-1.el9.x86_64.rpm" -OutFile "docker-ce-cli-26.1.4-1.el9.x86_64.rpm"

Invoke-WebRequest -Uri "https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-buildx-plugin-0.14.1-1.el9.x86_64.rpm" -OutFile "docker-buildx-plugin-0.14.1-1.el9.x86_64.rpm"

Invoke-WebRequest -Uri "https://download.docker.com/linux/rhel/9/x86_64/stable/Packages/docker-compose-plugin-2.27.1-1.el9.x86_64.rpm" -OutFile "docker-compose-plugin-2.27.1-1.el9.x86_64.rpm"
```

## After Downloading

Your `deploy/rpms/` folder should contain exactly these 5 files:
```
deploy/rpms/
├── containerd.io-1.6.31-3.1.el9.x86_64.rpm
├── docker-ce-26.1.4-1.el9.x86_64.rpm
├── docker-ce-cli-26.1.4-1.el9.x86_64.rpm
├── docker-buildx-plugin-0.14.1-1.el9.x86_64.rpm
└── docker-compose-plugin-2.27.1-1.el9.x86_64.rpm
```

The `setup.sh` script will install all of them automatically using:
```bash
rpm -ivh --nodeps deploy/rpms/*.rpm
```

## Note
These RPMs are for RHEL 9 x86_64 architecture only.
Do NOT use RHEL 8 or CentOS packages — they will fail on RHEL 9.