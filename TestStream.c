 #include <stdio.h>
 #include <fcntl.h>
 #include <stdlib.h>
 #include <unistd.h>
 #include <stdbool.h>
 #include <inttypes.h>
 #include <string.h>

 #define F_LINUX_SPECIFIC_BASE	1024
 #define F_GET_RW_HINT		(F_LINUX_SPECIFIC_BASE + 11)
 #define F_SET_RW_HINT		(F_LINUX_SPECIFIC_BASE + 12)

#define CHUNKSIZE 512*1024
#define MAX_STREAM 8
int main(int argc, char *argv[])
{
	uint64_t hint,StreamIdx;
	int fd[MAX_STREAM * 2], ret, writen, itrycount, istream, istreamcnt;
	char szFilePath[100],szPathPara[100], writeData[CHUNKSIZE];
	uint64_t iSize = 0;
	
	if (argc >= 3 )
	{
		strcpy(szPathPara,argv[1]);
		istream = atoi(argv[2]);
		itrycount = atoi(argv[3]);

		if (argc >= 4) 
			istreamcnt = atoi(argv[4]);
		else 
			istreamcnt = MAX_STREAM;

		printf("Test Path : %s, Stream on/off : %d, tricount : %d, StreamCount : %d \n", szPathPara, istream, itrycount, istreamcnt);
	}
	
	memset(writeData,'0',CHUNKSIZE);

	for( StreamIdx = 2 ; StreamIdx <= istreamcnt + 1; StreamIdx++ )
	{

		sprintf(szFilePath, "%s/TestStream_%d_%ld.txt",szPathPara,istream,StreamIdx);
	
		fd[StreamIdx] = open(szFilePath, O_RDWR|O_CREAT); 

		if (fd[StreamIdx] < 0) {printf("Open Error %s \n", szFilePath);}

		if (istream == 1)
		{		
			hint = StreamIdx;
			ret = fcntl(fd[StreamIdx], F_SET_RW_HINT, &hint);
			if (ret < 0) {	printf("Open Error : %s, hint : %ld\n", szFilePath, hint);}
		//	printf("File Open success : %s, with hint : %ld\n", szFilePath, hint);
		}
	}

	for ( int i = 0; i < itrycount; i++ )
	{			
		StreamIdx = i % istreamcnt + 2;

		writen = write(fd[StreamIdx], writeData, strlen(writeData));

		if (writen < 0) { printf("File write Fail : %s,hint : %ld\n", szFilePath, hint); }

		iSize = iSize + CHUNKSIZE;

		//printf("File Write success : %s, with hint : %ld\n", szFilePath, hint);
	}

	for( StreamIdx = 2 ; StreamIdx <= istreamcnt + 1; StreamIdx++ )
	{
		close(fd[StreamIdx]);
	}
	

	printf("File Write success Size: %ld \n", iSize);

	return 0;
}
